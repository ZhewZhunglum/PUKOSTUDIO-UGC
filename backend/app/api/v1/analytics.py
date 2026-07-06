from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tabular import (
    CSV_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    normalize_format,
    rows_to_csv_bytes,
    sheets_to_xlsx_bytes,
)
from app.dependencies import get_current_user
from app.models.user import User
from app.services import analytics_service

router = APIRouter()

_DAILY_COLUMNS = [
    "date", "emails_sent", "emails_delivered", "emails_opened", "emails_replied", "emails_bounced",
]


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


@router.get("/export")
async def export_dashboard(
    format: str = Query("csv"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fmt = normalize_format(format)
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    stats = (
        await analytics_service.get_dashboard_stats(
            db, current_user.team_id, start_date, end_date
        )
    )["stats"]
    daily = await analytics_service.get_daily_stats(
        db, current_user.team_id, start_date, end_date
    )

    daily_rows = [[d[col] for col in _DAILY_COLUMNS] for d in daily]
    filename = f"dashboard_{start_date}_{end_date}"

    if fmt == "xlsx":
        summary_rows = [["date_range", f"{start_date} ~ {end_date}"]] + [
            [k, v] for k, v in stats.items()
        ]
        body = sheets_to_xlsx_bytes([
            ("Summary", ["metric", "value"], summary_rows),
            ("Daily", _DAILY_COLUMNS, daily_rows),
        ])
        return Response(
            content=body,
            media_type=XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
        )

    # CSV can't hold two tables; export the daily breakdown.
    body = rows_to_csv_bytes(_DAILY_COLUMNS, daily_rows)
    return Response(
        content=body,
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
    )
