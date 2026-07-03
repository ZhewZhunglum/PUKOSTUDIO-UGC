from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import analytics_service

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    stats = await analytics_service.get_dashboard_stats(
        db, current_user.team_id, start_date, end_date
    )
    daily = await analytics_service.get_daily_stats(
        db, current_user.team_id, start_date, end_date
    )

    return {**stats, "daily": daily}
