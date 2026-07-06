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
):
    """Send a single email for a campaign."""
    from app.config import settings
    from app.integrations.email.manager import (
        apply_signature,
        get_email_sender,
        inject_tracking,
        select_best_account,
    )
    from app.models.campaign import CampaignInfluencer, CampaignInfluencerStatus, CampaignStep
    from app.models.email_account import EmailAccount
    from app.models.email_message import EmailDirection, EmailMessage, EmailStatus
    from app.models.influencer import Influencer
    from app.models.template import EmailTemplate
    from app.services.template_service import build_influencer_variables, render_template

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

        # Get first campaign step (MVP: single step)
        step = db.execute(
            select(CampaignStep)
            .where(CampaignStep.campaign_id == uuid.UUID(campaign_id))
            .order_by(CampaignStep.step_order)
        ).scalars().first()

        if not step:
            ci.status = CampaignInfluencerStatus.bounced
            logger.error(f"No steps found for campaign {campaign_id}")
            db.commit()
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
        rendered_subject, rendered_body = render_template(
            template.subject, template.body_html, variables
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
            metadata_={},
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # Inject tracking after the signature
        tracked_body = inject_tracking(signed_body, str(message.id), settings.base_url)

        # Send via provider
        sender = get_email_sender(account)
        message_id = asyncio.run(
            sender.send(
                from_address=f"{account.display_name or 'Team'} <{account.email_address}>",
                to_address=to_email,
                subject=rendered_subject,
                html_body=tracked_body,
                text_body=signed_text,
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

        db.commit()
        logger.info(f"Email sent to {to_email}, message_id: {message_id}")

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
            }
        db.commit()

        # A transient failure (SMTP timeout, provider 5xx / rate limit) should be
        # retried rather than permanently bouncing the influencer. Only give up —
        # and mark the enrollment bounced — once all retries are exhausted.
        try:
            raise self.retry(exc=e)
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
