from fastapi import APIRouter

from app.api.v1 import (
    ai,
    analytics,
    auth,
    campaigns,
    conversations,
    discovery,
    email_accounts,
    influencers,
    settings,
    sop,
    templates,
    tracking,
    uploads,
)
from app.api.v1.webhooks import inbound, sendgrid, ses

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(influencers.router, prefix="/influencers", tags=["Influencers"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(email_accounts.router, prefix="/email-accounts", tags=["Email Accounts"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(ai.router, tags=["AI Communication"])
api_router.include_router(sop.router, tags=["SOP"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(tracking.router, prefix="/track", tags=["Tracking"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["Discovery"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(ses.router, prefix="/webhooks/ses", tags=["Webhooks"])
api_router.include_router(sendgrid.router, prefix="/webhooks/sendgrid", tags=["Webhooks"])
api_router.include_router(inbound.router, prefix="/webhooks/inbound", tags=["Webhooks"])
