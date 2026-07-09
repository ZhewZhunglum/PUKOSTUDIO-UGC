import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.utils import get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# B2B outbound tracking/unsubscribe links use a distinct path prefix so they
# never collide with the influencer pipeline's /track/... routes.
_TRACK_PATH = "client-track"


@celery_app.task(name="app.workers.client_email_tasks.send_client_campaign_batch")
def send_client_campaign_batch(campaign_id: str, team_id: str, batch_size: int | None = None):
    """Process a batch of B2B client-outreach campaign emails."""
    from app.config import settings
    from app.models.client import Client
    from app.models.client_campaign import (
        ClientCampaign,
        ClientCampaignEnrollment,
        ClientCampaignInfluencerStatus,
        ClientCampaignStatus,
    )
    from app.services.sending_rules import seconds_until_send_window

    effective_batch_size = batch_size if batch_size is not None else settings.email_batch_size
    db = get_sync_session()
    try:
        campaign = db.execute(
            select(ClientCampaign).where(ClientCampaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()

        if not campaign or campaign.status != ClientCampaignStatus.active:
            logger.info(f"Client campaign {campaign_id} is not active, skipping batch")
            return

        window_delay = seconds_until_send_window(
            campaign.schedule_config, datetime.now(timezone.utc)
        )
        if window_delay > 0:
            logger.info(
                "Client campaign %s outside send window; retrying batch in %ss",
                campaign_id, window_delay,
            )
            send_client_campaign_batch.apply_async(
                args=[campaign_id, team_id, effective_batch_size],
                countdown=window_delay,
            )
            return

        queued = db.execute(
            select(ClientCampaignEnrollment)
            .where(
                ClientCampaignEnrollment.campaign_id == uuid.UUID(campaign_id),
                ClientCampaignEnrollment.status == ClientCampaignInfluencerStatus.queued,
            )
            .limit(effective_batch_size)
        ).scalars().all()

        if not queued:
            logger.info(f"Client campaign {campaign_id}: no more queued clients")
            return

        client_ids = [enrollment.client_id for enrollment in queued]
        clients_by_id = {
            c.id: c
            for c in db.execute(
                select(Client).where(Client.id.in_(client_ids))
            ).scalars().all()
        }

        for enrollment in queued:
            client = clients_by_id.get(enrollment.client_id)

            if not client or not client.email:
                enrollment.status = ClientCampaignInfluencerStatus.bounced
                continue

            delay = random.randint(30, 90)
            send_single_client_email.apply_async(
                args=[
                    str(enrollment.id),
                    campaign_id,
                    team_id,
                    str(client.id),
                    client.email,
                    client.contact_name or client.company_name,
                ],
                countdown=delay,
            )

            enrollment.status = ClientCampaignInfluencerStatus.in_progress

        db.commit()

        remaining = db.execute(
            select(ClientCampaignEnrollment)
            .where(
                ClientCampaignEnrollment.campaign_id == uuid.UUID(campaign_id),
                ClientCampaignEnrollment.status == ClientCampaignInfluencerStatus.queued,
            )
            .limit(1)
        ).scalar_one_or_none()

        if remaining:
            send_client_campaign_batch.apply_async(
                args=[campaign_id, team_id, effective_batch_size],
                countdown=settings.email_batch_delay_seconds,
            )
    except Exception as e:
        logger.error(f"Error processing client campaign batch: {e}")
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.workers.client_email_tasks.send_single_client_email",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def send_single_client_email(
    self,
    enrollment_id: str,
    campaign_id: str,
    team_id: str,
    client_id: str,
    to_email: str,
    client_name: str,
    step_order: int | None = None,
):
    """Send one campaign step's email to one B2B client.

    Mirrors ``email_tasks.send_single_email`` — see that function for the
    idempotency/retry/pause-resume rationale, which applies unchanged here.
    """
    from email_validator import EmailNotValidError, validate_email

    from app.config import settings
    from app.integrations.email.manager import (
        apply_signature,
        finalize_html_for_send,
        get_email_sender,
        inject_tracking,
        inject_unsubscribe,
        select_best_account,
        unsubscribe_headers,
    )
    from app.models.client import Client
    from app.models.client_campaign import (
        ClientCampaign,
        ClientCampaignEnrollment,
        ClientCampaignInfluencerStatus,
        ClientCampaignStatus,
        ClientCampaignStep,
    )
    from app.models.client_email_message import (
        ClientEmailDirection,
        ClientEmailMessage,
        ClientEmailStatus,
    )
    from app.models.email_account import EmailAccount
    from app.models.suppression import EmailSuppression, SuppressionReason
    from app.models.template import EmailTemplate
    from app.services import suppression_service
    from app.services.sending_rules import choose_ab_subject
    from app.services.template_service import build_client_variables, render_template

    _ALREADY_SENT = [
        ClientEmailStatus.sent, ClientEmailStatus.delivered,
        ClientEmailStatus.opened, ClientEmailStatus.clicked,
    ]

    db = get_sync_session()
    try:
        enrollment = db.execute(
            select(ClientCampaignEnrollment).where(
                ClientCampaignEnrollment.id == uuid.UUID(enrollment_id)
            )
        ).scalar_one_or_none()

        if not enrollment:
            return

        step_query = select(ClientCampaignStep).where(
            ClientCampaignStep.campaign_id == uuid.UUID(campaign_id)
        )
        if step_order is not None:
            step_query = step_query.where(ClientCampaignStep.step_order == step_order)
        step = db.execute(
            step_query.order_by(ClientCampaignStep.step_order)
        ).scalars().first()

        if not step:
            enrollment.status = ClientCampaignInfluencerStatus.bounced
            logger.error(
                "No step (order=%s) found for client campaign %s", step_order, campaign_id
            )
            db.commit()
            return

        already = db.execute(
            select(ClientEmailMessage.id).where(
                ClientEmailMessage.campaign_step_id == step.id,
                ClientEmailMessage.client_id == uuid.UUID(client_id),
                ClientEmailMessage.direction == ClientEmailDirection.outbound,
                ClientEmailMessage.status.in_(_ALREADY_SENT),
            )
        ).first()
        if already:
            logger.info(
                "Client %s already got step %s of campaign %s; skipping duplicate",
                client_id, step.step_order, campaign_id,
            )
            return

        campaign = db.execute(
            select(ClientCampaign).where(ClientCampaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign or campaign.status != ClientCampaignStatus.active:
            if enrollment.status == ClientCampaignInfluencerStatus.in_progress:
                enrollment.status = ClientCampaignInfluencerStatus.queued
                db.commit()
            logger.info(
                "Client campaign %s not active; deferring send for enrollment %s",
                campaign_id, enrollment_id,
            )
            return

        def _skip_permanently(reason: str, status: ClientCampaignInfluencerStatus) -> None:
            enrollment.status = status
            db.add(ClientEmailMessage(
                team_id=uuid.UUID(team_id),
                campaign_id=uuid.UUID(campaign_id),
                client_id=uuid.UUID(client_id),
                direction=ClientEmailDirection.outbound,
                from_address="",
                to_address=to_email,
                subject="(not sent)",
                status=ClientEmailStatus.failed,
                metadata_={"failure_reason": reason},
            ))
            db.commit()
            logger.info("Skipping send to %s: %s", to_email, reason)

        try:
            validate_email(to_email, check_deliverability=False)
        except EmailNotValidError as exc:
            _skip_permanently(f"邮箱地址无效: {exc}", ClientCampaignInfluencerStatus.bounced)
            return

        suppression = db.execute(
            select(EmailSuppression).where(
                EmailSuppression.team_id == uuid.UUID(team_id),
                EmailSuppression.email == suppression_service.normalize_email(to_email),
            )
        ).scalar_one_or_none()
        if suppression:
            terminal = (
                ClientCampaignInfluencerStatus.unsubscribed
                if suppression.reason == SuppressionReason.unsubscribed
                else ClientCampaignInfluencerStatus.bounced
            )
            _skip_permanently(f"收件人在抑制名单中（{suppression.reason.value}）", terminal)
            return

        template = db.execute(
            select(EmailTemplate).where(EmailTemplate.id == step.template_id)
        ).scalar_one_or_none()

        if not template:
            enrollment.status = ClientCampaignInfluencerStatus.bounced
            logger.error(f"Template {step.template_id} not found")
            db.commit()
            return

        accounts = db.execute(
            select(EmailAccount).where(
                EmailAccount.team_id == uuid.UUID(team_id),
                EmailAccount.is_active,
            )
        ).scalars().all()

        account = select_best_account(list(accounts), to_email.split("@")[-1])
        if not account:
            logger.warning("No available email accounts for client campaign %s", campaign_id)
            enrollment.status = ClientCampaignInfluencerStatus.bounced
            db.commit()
            return

        client = db.execute(
            select(Client).where(Client.id == uuid.UUID(client_id))
        ).scalar_one_or_none()
        variables = build_client_variables(client, fallback_name=client_name)

        subject_b = (step.condition or {}).get("ab_subject_b")
        has_experiment = bool(subject_b and str(subject_b).strip())
        raw_subject, ab_variant = choose_ab_subject(
            client_id, template.subject, subject_b
        )
        rendered_subject, rendered_body = render_template(
            raw_subject, template.body_html, variables
        )

        signed_body, signed_text = apply_signature(
            rendered_body, template.body_text, account
        )

        message = ClientEmailMessage(
            team_id=uuid.UUID(team_id),
            campaign_id=uuid.UUID(campaign_id),
            campaign_step_id=step.id,
            client_id=uuid.UUID(client_id),
            email_account_id=account.id,
            direction=ClientEmailDirection.outbound,
            from_address=account.email_address,
            to_address=to_email,
            subject=rendered_subject,
            body_html=signed_body,
            body_text=signed_text,
            status=ClientEmailStatus.sending,
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

        final_body = inject_unsubscribe(
            signed_body, str(message.id), settings.base_url, track_path=_TRACK_PATH
        )
        final_body = inject_tracking(
            final_body, str(message.id), settings.base_url, track_path=_TRACK_PATH
        )
        final_body = finalize_html_for_send(final_body)

        sender = get_email_sender(account)
        message_id = asyncio.run(
            sender.send(
                from_address=f"{account.display_name or 'Team'} <{account.email_address}>",
                to_address=to_email,
                subject=rendered_subject,
                html_body=final_body,
                text_body=signed_text,
                headers=unsubscribe_headers(
                    settings.base_url, str(message.id), track_path=_TRACK_PATH
                ),
            )
        )

        message.status = ClientEmailStatus.sent
        message.message_id = message_id
        message.sent_at = datetime.now(timezone.utc)

        db.execute(
            update(EmailAccount)
            .where(EmailAccount.id == account.id)
            .values(sent_today=EmailAccount.sent_today + 1)
        )

        enrollment.current_step = step.step_order
        enrollment.last_sent_at = datetime.now(timezone.utc)

        has_more = db.execute(
            select(ClientCampaignStep.id).where(
                ClientCampaignStep.campaign_id == uuid.UUID(campaign_id),
                ClientCampaignStep.step_order > step.step_order,
            )
        ).first()
        if not has_more:
            enrollment.status = ClientCampaignInfluencerStatus.completed

        db.commit()
        logger.info(
            f"Client email sent to {to_email} (step {step.step_order}, variant {ab_variant}), "
            f"message_id: {message_id}"
        )

    except Exception as e:
        logger.error(f"Error sending client email to {to_email}: {e}")
        db.rollback()

        failed_message = db.execute(
            select(ClientEmailMessage)
            .where(
                ClientEmailMessage.campaign_id == uuid.UUID(campaign_id),
                ClientEmailMessage.client_id == uuid.UUID(client_id),
            )
            .order_by(ClientEmailMessage.created_at.desc())
        ).scalars().first()
        if failed_message:
            failed_message.status = ClientEmailStatus.failed
            failed_message.metadata_ = {
                **(failed_message.metadata_ or {}),
                "failure_reason": str(e),
                "attempts": self.request.retries + 1,
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            }
        db.commit()

        try:
            countdown = min(60 * (2 ** self.request.retries), 3600)
            raise self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            enrollment = db.execute(
                select(ClientCampaignEnrollment).where(
                    ClientCampaignEnrollment.id == uuid.UUID(enrollment_id)
                )
            ).scalar_one_or_none()
            if enrollment:
                enrollment.status = ClientCampaignInfluencerStatus.bounced
            db.commit()
    finally:
        db.close()


@celery_app.task(name="app.workers.client_email_tasks.process_client_followups")
def process_client_followups():
    """Dispatch due follow-up steps for active multi-step client campaigns.

    Mirrors ``email_tasks.process_followups`` — runs periodically via beat.
    """
    from app.models.client import Client
    from app.models.client_campaign import (
        ClientCampaign,
        ClientCampaignEnrollment,
        ClientCampaignInfluencerStatus,
        ClientCampaignStatus,
        ClientCampaignStep,
    )
    from app.services.sending_rules import next_due_step, seconds_until_send_window

    now = datetime.now(timezone.utc)
    db = get_sync_session()
    dispatched = 0
    try:
        campaigns = db.execute(
            select(ClientCampaign).where(ClientCampaign.status == ClientCampaignStatus.active)
        ).scalars().all()

        for campaign in campaigns:
            steps = db.execute(
                select(ClientCampaignStep).where(ClientCampaignStep.campaign_id == campaign.id)
            ).scalars().all()
            if len(steps) <= 1:
                continue
            if seconds_until_send_window(campaign.schedule_config, now) > 0:
                continue

            enrollments = db.execute(
                select(ClientCampaignEnrollment).where(
                    ClientCampaignEnrollment.campaign_id == campaign.id,
                    ClientCampaignEnrollment.status == ClientCampaignInfluencerStatus.in_progress,
                )
            ).scalars().all()
            if not enrollments:
                continue

            clients_by_id = {
                c.id: c
                for c in db.execute(
                    select(Client).where(
                        Client.id.in_([enrollment.client_id for enrollment in enrollments])
                    )
                ).scalars().all()
            }

            for enrollment in enrollments:
                nxt = next_due_step(steps, enrollment.current_step, enrollment.last_sent_at, now)
                if not nxt:
                    continue
                client = clients_by_id.get(enrollment.client_id)
                if not client or not client.email:
                    enrollment.status = ClientCampaignInfluencerStatus.bounced
                    continue
                send_single_client_email.apply_async(
                    args=[
                        str(enrollment.id),
                        str(campaign.id),
                        str(campaign.team_id),
                        str(client.id),
                        client.email,
                        client.contact_name or client.company_name,
                    ],
                    kwargs={"step_order": nxt.step_order},
                    countdown=random.randint(5, 60),
                )
                dispatched += 1

        db.commit()
        if dispatched:
            logger.info("Dispatched %s client follow-up send(s)", dispatched)
    finally:
        db.close()
