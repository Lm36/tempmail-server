"""Background cleanup job for expired addresses"""

import time
import logging
from sqlalchemy import text

from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)


def cleanup_expired_addresses():
    """
    Delete expired addresses and their associated emails.

    This is run periodically as a background task.
    """
    db = SessionLocal()
    try:
        # Call the database function to cleanup
        result = db.execute(text("SELECT cleanup_expired_addresses()"))
        deleted_count = result.scalar()

        if deleted_count and deleted_count > 0:
            logger.info(f"Cleanup: Deleted {deleted_count} expired addresses")
        else:
            logger.debug("Cleanup: No expired addresses to delete")

        db.commit()

    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        db.rollback()

    finally:
        db.close()


def run_cleanup_loop():
    """
    Run cleanup in an infinite loop.

    This is meant to be run in a separate thread or process.
    """
    interval_seconds = settings.CLEANUP_INTERVAL_HOURS * 3600

    logger.info(f"Starting cleanup loop (interval: {settings.CLEANUP_INTERVAL_HOURS}h)")

    while True:
        try:
            cleanup_expired_addresses()
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}")

        # Sleep until next run
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run cleanup loop
    run_cleanup_loop()
