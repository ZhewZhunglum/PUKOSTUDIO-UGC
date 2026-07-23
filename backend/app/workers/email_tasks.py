import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.utils import get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.email_tasks.send_campaign_batch")
def send_campaign_batch(campaign_id: str, team_id: str, batch_size: int | None = None):
    """Process a batch of campaign emails."""
    from app.config import settings
    from app.models.campaign import (
        Campaign,
        CampaignInfluencer,
        CampaignInfluencerStatus,
        CampaignStatus,
    )
    from app.models.influencer import Influencer
    from app.services.sending_rules import seconds_until_send_window

    effective_batch_size = batch_size if batch_size is not None else settings.email_batch_size
    db = get_sync_session()
    try:
        # Verify campaign is still active
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()

        if not campaign or campaign.status != CampaignStatus.active:
            logger.info(f"Campaign {campaign_id} is not active, skipping batch")
            return

        # Honor the campaign's send window (schedule_config.send_window): outside
        # it, re-schedule this batch for when the window opens in the configured
        # timezone instead of dispatching mail at 3am recipient time.
        window_delay = seconds_until_send_window(
            campaign.schedule_config, datetime.now(timezone.utc)
        )
        if window_delay > 0:
            logger.info(
                "Campaign %s outside send window; retrying batch in %ss",
                campaign_id, window_delay,
            )
            send_campaign_batch.apply_async(
                args=[campaign_id, team_id, effective_batch_size],
                countdown=window_delay,
            )
            return

        # Get queued influencers
        queued = db.execute(
            select(CampaignInfluencer)
            .where(
                CampaignInfluencer.campaign_id == uuid.UUID(campaign_id),
                CampaignInfluencer.status == CampaignInfluencerStatus.queued,
            )
            .limit(effective_batch_size)
        ).scalars().all()

        if not queued:
            logger.info(f"Campaign {campaign_id}: no more queued influencers")
            return

        # Batch-load all influencers to avoid N+1 queries
        influencer_ids = [ci.influencer_id for ci in queued]
        influencers_by_id = {
            inf.id: inf
            for inf in db.execute(
                select(Influencer).where(Influencer.id.in_(influencer_ids))
            ).scalars().all()
        }

        for ci in queued:
            influencer = influencers_by_id.get(ci.influencer_id)

            if not influencer or not influencer.email:
                ci.status = CampaignInfluencerStatus.bounced
                continue

            # Dispatch individual send with staggered delay
            delay = random.randint(30, 90)
            send_single_email.apply_async(
                args=[
                    str(ci.id),
                    campaign_id,
                    team_id,
                    str(influencer.id),
                    influencer.email,
                    influencer.name,
                ],
                countdown=delay,
            )

            ci.status = CampaignInfluencerStatus.in_progress

        # Single commit after all mutations are staged
        db.commit()

        # Schedule next batch if there are more
        remaining = db.execute(
            select(CampaignInfluencer)
            .where(
                CampaignInfluencer.campaign_id == uuid.UUID(campaign_id),
                CampaignInfluencer.status == CampaignInfluencerStatus.queued,
            )
            .limit(1)
        ).scalar_one_or_none()

        if remaining:
            send_campaign_batch.apply_async(
                args=[campaign_id, team_id, effective_batch_size],
                countdown=settings.email_batch_delay_seconds,
            )
    except Exception as e:
        logger.error(f"Error processing campaign batch: {e}")
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.workers.email_tasks.send_single_email",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def send_single_email(
    self,
    campaign_influencer_id: str,
    campaign_id: str,
    team_id: str,
    influencer_id: str,
    to_email: str,
    influencer_name: str,
    step_order: int | None = None,
):
    """Send one campaign step's email to one influencer.

    ``step_order`` selects the sequence step (None = the initial step); the
    batch task dispatches step 1 and process_followups dispatches later steps.
    """
    from email_validator import EmailNotValidError, validate_email

    from app.config import settings
    from app.integrations.email.manager import (
        apply_signature,
        finalize_html_for_send,
        get_email_sender,
        inject_tracking,
        inject_unsubscribe,
        rewrite_links_for_tracking,
        select_best_account,
        unsubscribe_headers,
    )
    from app.models.campaign import (
        Campaign,
        CampaignInfluencer,
        CampaignInfluencerStatus,
        CampaignStatus,
        CampaignStep,
    )
    from app.models.email_account import EmailAccount
    from app.models.email_message import EmailDirection, EmailMessage, EmailStatus
    from app.models.influencer import Influencer
    from app.models.suppression import EmailSuppression, SuppressionReason
    from app.models.template import EmailTemplate
    from app.services import suppression_service
    from app.services.attachment_service import attachment_payloads_for_ids_sync
    from app.services.sending_rules import choose_ab_subject
    from app.services.template_service import build_influencer_variables, render_template

    # Statuses that mean "this influencer already received the campaign email".
    _ALREADY_SENT = [
        EmailStatus.sent, EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked,
    ]

    db = get_sync_session()
    try:
        # Get campaign influencer record
        ci = db.execute(
            select(CampaignInfluencer).where(
                CampaignInfluencer.id == uuid.UUID(campaign_influencer_id)
            )
        ).scalar_one_or_none()

        if not ci:
            return

        # Resolve the sequence step to send (None = the initial step).
        step_query = select(CampaignStep).where(
            CampaignStep.campaign_id == uuid.UUID(campaign_id)
        )
        if step_order is not None:
            step_query = step_query.where(CampaignStep.step_order == step_order)
        step = db.execute(
            step_query.order_by(CampaignStep.step_order)
        ).scalars().first()

        if not step:
            ci.status = CampaignInfluencerStatus.bounced
            logger.error(
                "No step (order=%s) found for campaign %s", step_order, campaign_id
            )
            db.commit()
            return

        # Per-step idempotency: if this influencer already has a sent (or
        # further) outbound message for THIS step, do not send again. Protects
        # against Celery redelivery, double dispatch, and re-runs after a resume
        # — while still allowing later follow-up steps to send.
        already = db.execute(
            select(EmailMessage.id).where(
                EmailMessage.campaign_step_id == step.id,
                EmailMessage.influencer_id == uuid.UUID(influencer_id),
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_(_ALREADY_SENT),
            )
        ).first()
        if already:
            logger.info(
                "Influencer %s already got step %s of campaign %s; skipping duplicate",
                influencer_id, step.step_order, campaign_id,
            )
            return

        # Honor pause/stop: only send while the campaign is active. If it was
        # paused/stopped after this task was queued, reset the enrollment to
        # queued so a later resume re-dispatches it (断点续发) rather than sending
        # into a paused campaign or stranding it in_progress.
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign or campaign.status != CampaignStatus.active:
            if ci.status == CampaignInfluencerStatus.in_progress:
                ci.status = CampaignInfluencerStatus.queued
                db.commit()
            logger.info(
                "Campaign %s not active; deferring send for enrollment %s",
                campaign_id, campaign_influencer_id,
            )
            return

        def _skip_permanently(reason: str, status: CampaignInfluencerStatus) -> None:
            """Mark the enrollment terminally skipped and leave an audit message."""
            ci.status = status
            db.add(EmailMessage(
                team_id=uuid.UUID(team_id),
                campaign_id=uuid.UUID(campaign_id),
                influencer_id=uuid.UUID(influencer_id),
                direction=EmailDirection.outbound,
                from_address="",
                to_address=to_email,
                subject="(not sent)",
                status=EmailStatus.failed,
                metadata_={"failure_reason": reason},
            ))
            db.commit()
            logger.info("Skipping send to %s: %s", to_email, reason)

        # Pre-send validation: a syntactically invalid address can never be
        # delivered — fail fast instead of burning a provider call and a bounce.
        try:
            validate_email(to_email, check_deliverability=False)
        except EmailNotValidError as exc:
            _skip_permanently(f"邮箱地址无效: {exc}", CampaignInfluencerStatus.bounced)
            return

        # Suppression list: never mail addresses that bounced, complained, or
        # unsubscribed. This is the core deliverability guard.
        suppression = db.execute(
            select(EmailSuppression).where(
                EmailSuppression.team_id == uuid.UUID(team_id),
                EmailSuppression.email == suppression_service.normalize_email(to_email),
            )
        ).scalar_one_or_none()
        if suppression:
            terminal = (
                CampaignInfluencerStatus.unsubscribed
                if suppression.reason == SuppressionReason.unsubscribed
                else CampaignInfluencerStatus.bounced
            )
            _skip_permanently(f"收件人在抑制名单中（{suppression.reason.value}）", terminal)
            return

        # Get template
        template = db.execute(
            select(EmailTemplate).where(EmailTemplate.id == step.template_id)
        ).scalar_one_or_none()

        if not template:
            ci.status = CampaignInfluencerStatus.bounced
            logger.error(f"Template {step.template_id} not found")
            db.commit()
            return

        # Select email account
        accounts = db.execute(
            select(EmailAccount).where(
                EmailAccount.team_id == uuid.UUID(team_id),
                EmailAccount.is_active,
            )
        ).scalars().all()

        account = select_best_account(list(accounts), to_email.split("@")[-1])
        if not account:
            logger.warning("No available email accounts for campaign %s", campaign_id)
            ci.status = CampaignInfluencerStatus.bounced
            db.commit()
            return

        # Render template. Load the full influencer so template variables like
        # {{email}}, {{niche}}, {{platform}}, {{username}}, {{followers}} resolve;
        # otherwise those placeholders would ship verbatim to the recipient.
        influencer = db.execute(
            select(Influencer).where(Influencer.id == uuid.UUID(influencer_id))
        ).scalar_one_or_none()
        variables = build_influencer_variables(influencer, fallback_name=influencer_name)

        # A/B subject test: when the step defines an alternative subject
        # (condition.ab_subject_b), split deterministically 50/50 by influencer
        # id so retries always pick the same variant. Steps without an
        # experiment record no variant, keeping the stats comparison clean.
        subject_b = (step.condition or {}).get("ab_subject_b")
        has_experiment = bool(subject_b and str(subject_b).strip())
        raw_subject, ab_variant = choose_ab_subject(
            influencer_id, template.subject, subject_b
        )
        rendered_subject, rendered_body = render_template(
            raw_subject, template.body_html, variables
        )

        # Append branded signature (before tracking) so the pixel stays last.
        signed_body, signed_text = apply_signature(
            rendered_body, template.body_text, account
        )

        # Create message record
        message = EmailMessage(
            team_id=uuid.UUID(team_id),
            campaign_id=uuid.UUID(campaign_id),
            campaign_step_id=step.id,
            influencer_id=uuid.UUID(influencer_id),
            email_account_id=account.id,
            direction=EmailDirection.outbound,
            from_address=account.email_address,
            to_address=to_email,
            subject=rendered_subject,
            body_html=signed_body,
            body_text=signed_text,
            status=EmailStatus.sending,
            metadata_={
                "attempts": self.request.retries + 1,
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                "step_order": step.step_order,
                **({"ab_variant": ab_variant} if has_experiment else {}),
            },
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # Rewrite content links to a click-tracking redirect BEFORE adding the
        # unsubscribe footer, so that link is never itself wrapped. Then inject
        # the unsubscribe footer, then the open-tracking pixel (pixel stays last).
        final_body = rewrite_links_for_tracking(signed_body, str(message.id), settings.base_url)
        final_body = inject_unsubscribe(final_body, str(message.id), settings.base_url)
        final_body = inject_tracking(final_body, str(message.id), settings.base_url)
        # Inline CSS as the last transform before the network call, so
        # WYSIWYG-authored <style> blocks/classes render consistently across
        # Gmail/Outlook/Apple Mail. The stored message.body_html above stays
        # pre-inline (rendering-only transform, no semantic content change).
        final_body = finalize_html_for_send(final_body)

        # Load the step's configured attachments, if any (team-scoped; ids the
        # team no longer owns are silently skipped, matching the reply-send path).
        attachment_payloads = attachment_payloads_for_ids_sync(
            db, uuid.UUID(team_id), [uuid.UUID(a) for a in (step.attachment_ids or [])]
        )

        # Send via provider with RFC 8058 one-click unsubscribe headers —
        # mailbox providers weigh these heavily for bulk-sender reputation.
        sender = get_email_sender(account)
        message_id = asyncio.run(
            sender.send(
                from_address=f"{account.display_name or 'Team'} <{account.email_address}>",
                to_address=to_email,
                subject=rendered_subject,
                html_body=final_body,
                text_body=signed_text,
                headers=unsubscribe_headers(settings.base_url, str(message.id)),
                attachments=attachment_payloads or None,
            )
        )

        # Update status
        message.status = EmailStatus.sent
        message.message_id = message_id
        message.sent_at = datetime.now(timezone.utc)

        # Atomically bump the daily counter so concurrent sends can't clobber
        # each other's increment (a read-modify-write on account.sent_today
        # loses updates and lets the daily limit be exceeded).
        db.execute(
            update(EmailAccount)
            .where(EmailAccount.id == account.id)
            .values(sent_today=EmailAccount.sent_today + 1)
        )

        # Update campaign influencer
        ci.current_step = step.step_order
        ci.last_sent_at = datetime.now(timezone.utc)

        # Sequence finished? Mark completed so follow-up scans skip this
        # enrollment; a later reply still flips it to replied via intent mapping.
        has_more = db.execute(
            select(CampaignStep.id).where(
                CampaignStep.campaign_id == uuid.UUID(campaign_id),
                CampaignStep.step_order > step.step_order,
            )
        ).first()
        if not has_more:
            ci.status = CampaignInfluencerStatus.completed

        db.commit()
        logger.info(
            f"Email sent to {to_email} (step {step.step_order}, variant {ab_variant}), "
            f"message_id: {message_id}"
        )

    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        db.rollback()

        # Record the failure on the most recent message for this send attempt.
        failed_message = db.execute(
            select(EmailMessage)
            .where(
                EmailMessage.campaign_id == uuid.UUID(campaign_id),
                EmailMessage.influencer_id == uuid.UUID(influencer_id),
            )
            .order_by(EmailMessage.created_at.desc())
        ).scalars().first()
        if failed_message:
            failed_message.status = EmailStatus.failed
            failed_message.metadata_ = {
                **(failed_message.metadata_ or {}),
                "failure_reason": str(e),
                "attempts": self.request.retries + 1,
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            }
        db.commit()

        # A transient failure (SMTP timeout, provider 5xx / rate limit) should be
        # retried with exponential backoff rather than permanently bouncing the
        # influencer. Only give up — and mark the enrollment bounced — once all
        # retries are exhausted.
        try:
            countdown = min(60 * (2 ** self.request.retries), 3600)
            raise self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            ci = db.execute(
                select(CampaignInfluencer).where(
                    CampaignInfluencer.id == uuid.UUID(campaign_influencer_id)
                )
            ).scalar_one_or_none()
            if ci:
                ci.status = CampaignInfluencerStatus.bounced
            db.commit()
    finally:
        db.close()


@celery_app.task(name="app.workers.email_tasks.process_followups")
def process_followups():
    """Dispatch due follow-up steps for active multi-step campaigns.

    Runs periodically via beat. An enrollment gets the next step when it is
    still in_progress (no reply/bounce/unsubscribe), the previous step was sent
    long enough ago (next step's delay_days), and the campaign is inside its
    send window. Per-step idempotency in send_single_email makes double
    dispatch harmless.
    """
    from app.models.campaign import (
        Campaign,
        CampaignInfluencer,
        CampaignInfluencerStatus,
        CampaignStatus,
        CampaignStep,
    )
    from app.models.influencer import Influencer
    from app.services.sending_rules import next_due_step, seconds_until_send_window

    now = datetime.now(timezone.utc)
    db = get_sync_session()
    dispatched = 0
    try:
        campaigns = db.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.active)
        ).scalars().all()

        for campaign in campaigns:
            steps = db.execute(
                select(CampaignStep).where(CampaignStep.campaign_id == campaign.id)
            ).scalars().all()
            if len(steps) <= 1:
                continue  # single-step campaigns have no follow-ups
            if seconds_until_send_window(campaign.schedule_config, now) > 0:
                continue  # outside send window; next beat run retries

            enrollments = db.execute(
                select(CampaignInfluencer).where(
                    CampaignInfluencer.campaign_id == campaign.id,
                    CampaignInfluencer.status == CampaignInfluencerStatus.in_progress,
                )
            ).scalars().all()
            if not enrollments:
                continue

            influencers_by_id = {
                inf.id: inf
                for inf in db.execute(
                    select(Influencer).where(
                        Influencer.id.in_([ci.influencer_id for ci in enrollments])
                    )
                ).scalars().all()
            }

            for ci in enrollments:
                nxt = next_due_step(steps, ci.current_step, ci.last_sent_at, now)
                if not nxt:
                    continue
                influencer = influencers_by_id.get(ci.influencer_id)
                if not influencer or not influencer.email:
                    ci.status = CampaignInfluencerStatus.bounced
                    continue
                send_single_email.apply_async(
                    args=[
                        str(ci.id),
                        str(campaign.id),
                        str(campaign.team_id),
                        str(influencer.id),
                        influencer.email,
                        influencer.name,
                    ],
                    kwargs={"step_order": nxt.step_order},
                    countdown=random.randint(5, 60),
                )
                dispatched += 1

        db.commit()
        if dispatched:
            logger.info("Dispatched %s follow-up send(s)", dispatched)
    finally:
        db.close()


@celery_app.task(name="app.workers.email_tasks.reset_daily_counts")
def reset_daily_counts():
    """Reset daily email send counts for all accounts. Runs at midnight UTC."""
    from app.models.email_account import EmailAccount

    db = get_sync_session()
    try:
        db.execute(update(EmailAccount).values(sent_today=0))
        db.commit()
        logger.info("Daily email counts reset")
    finally:
        db.close()


@celery_app.task(name="app.workers.email_tasks.advance_warmup")
def advance_warmup():
    """Advance the warmup stage of healthy accounts that actually sent mail.

    Runs daily (before reset_daily_counts zeroes the counters). An account moves
    up one stage only when it is healthy and sent something today — idle or
    degraded accounts stay put, so the ramp never outruns real sending history.
    """
    from app.integrations.email.manager import WARMUP_CAPS
    from app.models.email_account import EmailAccount, EmailHealthStatus

    max_stage = len(WARMUP_CAPS)
    db = get_sync_session()
    try:
        result = db.execute(
            update(EmailAccount)
            .where(
                EmailAccount.is_active,
                EmailAccount.health_status == EmailHealthStatus.healthy,
                EmailAccount.sent_today > 0,
                EmailAccount.warmup_stage < max_stage,
            )
            .values(warmup_stage=EmailAccount.warmup_stage + 1)
        )
        db.commit()
        logger.info("Advanced warmup stage for %s account(s)", result.rowcount)
    finally:
        db.close()
