import uuid
from datetime import date

from sqlalchemy.dialects import postgresql

from app.config import settings
from app.services.analytics_service import daily_stats_query


def test_daily_stats_query_reuses_single_timezone_bind(monkeypatch):
    """Regression guard for the GROUP BY timezone bug.

    The per-day date expression must be one reused object so the timezone value
    is a single bind parameter shared by SELECT / GROUP BY / ORDER BY. If it were
    rebuilt per clause, each clause would get a distinct parameter and Postgres
    would raise "column must appear in the GROUP BY clause".
    """
    monkeypatch.setattr(settings, "reporting_timezone", "Asia/Shanghai")

    stmt = daily_stats_query(uuid.uuid4(), date(2026, 1, 1), date(2026, 1, 31))
    compiled = stmt.compile(dialect=postgresql.dialect())

    tz_binds = [v for v in compiled.params.values() if v == "Asia/Shanghai"]
    assert len(tz_binds) == 1, (
        f"expected the timezone to be a single reused bind parameter, "
        f"got {len(tz_binds)} — the date expression is being rebuilt per clause"
    )

    sql = str(compiled)
    assert "GROUP BY" in sql


def test_daily_stats_query_includes_a_clicked_column():
    """click_rate (analytics_service.get_daily_stats) reads row.clicked — the
    query must actually project that column, not just open_rate's opened/delivered.
    """
    stmt = daily_stats_query(uuid.uuid4(), date(2026, 1, 1), date(2026, 1, 31))
    compiled = stmt.compile(dialect=postgresql.dialect())

    assert "AS clicked" in str(compiled)
