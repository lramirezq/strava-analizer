"""Activity sync — downloads activities from Strava to SQLite.

Run directly:
    python -m app.sync
"""

import logging
import time
from datetime import datetime

from app.config import validate_config
from app.db import get_activity_count, get_latest_activity_timestamp, init_db, upsert_activity
from app.strava_client import StravaAuthError, fetch_activities

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def sync_activities() -> None:
    """Download all activities from Strava, incrementally if data exists."""
    validate_config()
    init_db()

    latest = get_latest_activity_timestamp()
    after_epoch: int | None = None
    if latest:
        dt = datetime.fromisoformat(latest)
        after_epoch = int(dt.timestamp())
        logger.info(f"Incremental sync: activities after {latest}")
    else:
        logger.info("Full sync: downloading all activities...")

    page = 1
    total_synced = 0
    total_before = get_activity_count()

    while True:
        retries = 0
        activities = None

        while retries < MAX_RETRIES:
            try:
                activities = fetch_activities(after=after_epoch, page=page)
                break
            except StravaAuthError:
                logger.error("Auth failed. Run 'python -m app.auth'.")
                return
            except RuntimeError as e:
                retries += 1
                if retries >= MAX_RETRIES:
                    logger.error(f"Failed after {MAX_RETRIES} retries. Stopping.")
                    logger.info(f"Partial sync: {total_synced} activities saved.")
                    return
                logger.warning(f"Error page {page}: {e}. Retry {retries}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY_SECONDS * retries)

        if not activities:
            break

        for activity in activities:
            upsert_activity(activity)
            total_synced += 1

        logger.info(f"Page {page}: {len(activities)} activities (total: {total_synced})")

        if len(activities) < 200:
            break

        page += 1
        time.sleep(0.5)

    total_after = get_activity_count()
    new_count = total_after - total_before
    print("\n✅ Sync complete!")
    print(f"   New activities: {new_count}")
    print(f"   Total in database: {total_after}")


if __name__ == "__main__":
    sync_activities()
