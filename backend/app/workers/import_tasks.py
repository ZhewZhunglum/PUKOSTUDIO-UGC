import csv
import io
import logging
import uuid

from app.core.utils import get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.import_tasks.process_csv_import")
def process_csv_import(team_id: str, csv_content: str):
    """Process a CSV import asynchronously for large files."""
    from app.models.influencer import Influencer, InfluencerPlatform, Platform

    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    db = get_sync_session()

    imported = 0
    skipped = 0
    errors = []

    try:
        for i, row in enumerate(rows):
            try:
                name = row.get("name", "").strip()
                email = row.get("email", "").strip() or None

                if not name:
                    errors.append(f"Row {i + 1}: Missing name")
                    skipped += 1
                    continue

                if email:
                    existing = db.query(Influencer).filter(
                        Influencer.email == email,
                        Influencer.team_id == uuid.UUID(team_id),
                    ).first()
                    if existing:
                        skipped += 1
                        continue

                # Persist each row inside its own SAVEPOINT so a single bad row
                # only rolls back that row, not the up-to-99 rows already staged
                # since the last commit.
                with db.begin_nested():
                    influencer = Influencer(
                        team_id=uuid.UUID(team_id),
                        name=name,
                        email=email,
                        niche=row.get("niche", "").strip() or None,
                        country=row.get("country", "US").strip() or "US",
                        source="csv_import",
                    )
                    db.add(influencer)
                    db.flush()

                    platform_name = row.get("platform", "").strip().lower()
                    username = row.get("username", "").strip()
                    if platform_name and username and platform_name in ("tiktok", "instagram", "youtube"):
                        followers_str = row.get("followers", "")
                        followers = int(followers_str) if followers_str and str(followers_str).isdigit() else None
                        platform = InfluencerPlatform(
                            team_id=uuid.UUID(team_id),
                            influencer_id=influencer.id,
                            platform=Platform(platform_name),
                            username=username,
                            followers=followers,
                        )
                        db.add(platform)

                imported += 1

                # Periodically release savepoints and persist progress.
                if imported % 100 == 0:
                    db.commit()

            except Exception as e:
                # Only this row's savepoint was rolled back; staged rows survive.
                errors.append(f"Row {i + 1}: {str(e)}")
                skipped += 1

        db.commit()
        logger.info(
            f"CSV import complete for team {team_id}: "
            f"{imported} imported, {skipped} skipped, {len(errors)} errors"
        )
        return {"imported": imported, "skipped": skipped, "errors": errors[:50]}

    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
