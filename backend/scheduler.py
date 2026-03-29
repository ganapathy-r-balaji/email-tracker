"""
scheduler.py – APScheduler background sync.

Runs run_sync() for all users with stored refresh tokens every N minutes
(configured via SYNC_INTERVAL_MINUTES env var, default 30).
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import GmailAccount, User

_scheduler = BackgroundScheduler()


def _sync_all_users():
    """Called by APScheduler on the configured interval."""
    from routers.sync import run_sync  # local import to avoid circular deps

    db = SessionLocal()
    try:
        # Find distinct users who have at least one connected GmailAccount
        user_ids = [
            row[0]
            for row in db.query(GmailAccount.user_id).distinct().all()
        ]
        print(f"[Scheduler] Syncing {len(user_ids)} user(s)...")
        for user_id in user_ids:
            try:
                run_sync(user_id)
            except Exception as exc:
                print(f"[Scheduler] Sync failed for user {user_id}: {exc}")
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler. Call this once on application startup."""
    interval = int(os.getenv("SYNC_INTERVAL_MINUTES", 30))

    _scheduler.add_job(
        _sync_all_users,
        trigger="interval",
        minutes=interval,
        id="sync_all_users",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping sync jobs
    )
    _scheduler.start()
    print(f"⏰ Scheduler started – syncing every {interval} minute(s).")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
