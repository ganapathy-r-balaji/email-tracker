"""
scheduler.py – APScheduler background sync.

Runs run_sync() for all users with stored refresh tokens every N minutes
(configured via SYNC_INTERVAL_MINUTES env var, default 30).
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import User

_scheduler = BackgroundScheduler()


def _sync_all_users():
    """Called by APScheduler on the configured interval."""
    from routers.sync import run_sync  # local import to avoid circular deps

    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.gmail_refresh_token.isnot(None))
            .all()
        )
        print(f"[Scheduler] Syncing {len(users)} user(s)...")
        for user in users:
            try:
                run_sync(user.id)
            except Exception as exc:
                print(f"[Scheduler] Sync failed for user {user.id}: {exc}")
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
