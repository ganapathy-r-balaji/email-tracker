"""
routers/sync.py – Email sync orchestration.

POST /api/sync  – trigger a manual sync for the authenticated user (runs in background)
GET  /api/sync/status – get sync status / last_sync_at for the current user
"""

import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import get_current_user, get_valid_google_credentials
from database import SessionLocal, get_db
from models import EmailCategory, EmailLog, User
from services.classifier import classify_email
from services.extractor import extract_order_data
from services.gmail import build_gmail_service, get_email_details, search_order_emails
from services.linker import link_and_store

router = APIRouter()

MAX_RESULTS = int(os.getenv("EMAIL_SYNC_MAX_RESULTS", 200))


# ─── Trigger sync ─────────────────────────────────────────────────────────────
@router.post("/api/sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Trigger an email sync for the authenticated user.
    Runs in the background so the HTTP response is immediate.
    """
    if not current_user.gmail_refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No Gmail refresh token stored. Please reconnect your Gmail account.",
        )

    background_tasks.add_task(run_sync, current_user.id)
    return {"status": "sync_started", "message": "Email sync is running in the background."}


# ─── Sync status ──────────────────────────────────────────────────────────────
@router.get("/api/sync/status")
def sync_status(current_user: User = Depends(get_current_user)):
    """Return when the last sync completed."""
    return {
        "last_sync_at": current_user.last_sync_at.isoformat() if current_user.last_sync_at else None,
    }


# ─── Core sync pipeline ───────────────────────────────────────────────────────
def run_sync(user_id: int):
    """
    Full email sync pipeline for a single user.

    1. Load user + credentials
    2. Fetch order-related Gmail message IDs
    3. Filter already-processed IDs (deduplication via email_log)
    4. For each new email:
       a. Fetch full email details
       b. Classify with Claude
       c. Extract structured data with Claude (if not irrelevant)
       d. Link/store to Order, Item, Shipment tables
       e. Write EmailLog record
    5. Update user.last_sync_at
    """
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"[Sync] User {user_id} not found, skipping.")
            return

        print(f"[Sync] Starting sync for {user.email}")

        # ── Step 1: Get valid credentials (auto-refresh if expired) ──────────
        try:
            credentials = get_valid_google_credentials(user)
        except Exception as exc:
            print(f"[Sync] Failed to get credentials for user {user_id}: {exc}")
            return

        # Persist refreshed access token if it changed
        if credentials.token:
            from auth_utils import encrypt_token
            user.gmail_access_token = encrypt_token(credentials.token)
            user.token_expiry = credentials.expiry
            db.commit()

        # ── Step 2: Fetch email IDs from Gmail ───────────────────────────────
        gmail = build_gmail_service(credentials)
        print(f"[Sync] Fetching up to {MAX_RESULTS} email IDs...")
        all_ids = search_order_emails(gmail, max_results=MAX_RESULTS)
        print(f"[Sync] Found {len(all_ids)} candidate emails.")

        # ── Step 3: Filter already-processed emails ──────────────────────────
        existing_ids = {
            row[0]
            for row in db.query(EmailLog.gmail_message_id)
            .filter(EmailLog.user_id == user_id)
            .all()
        }
        new_ids = [eid for eid in all_ids if eid not in existing_ids]
        print(f"[Sync] {len(new_ids)} new emails to process (skipping {len(existing_ids)} already processed).")

        # ── Step 4: Process each new email ───────────────────────────────────
        processed = 0
        for email_id in new_ids:
            try:
                _process_single_email(db, user, gmail, email_id)
                processed += 1
            except Exception as exc:
                print(f"[Sync] Error processing email {email_id}: {exc}")
                # Log the email as processed (with no category) to avoid infinite retries
                _log_email(db, user_id, email_id, {}, "error", None)

        # ── Step 5: Update last_sync_at ──────────────────────────────────────
        user.last_sync_at = datetime.utcnow()
        db.commit()
        print(f"[Sync] Done. Processed {processed}/{len(new_ids)} new emails for {user.email}.")

    except Exception as exc:
        print(f"[Sync] Unhandled error for user {user_id}: {exc}")
    finally:
        db.close()


def _process_single_email(db: Session, user: User, gmail, email_id: str):
    """Fetch, classify, extract, link, and log a single email."""

    # Fetch email details
    email = get_email_details(gmail, email_id)

    # Classify
    classification = classify_email(
        subject=email["subject"],
        from_addr=email["from"],
        body=email["body_text"],
    )
    category = classification.get("category", EmailCategory.IRRELEVANT)

    # Skip low-confidence irrelevant emails
    if category == EmailCategory.IRRELEVANT:
        _log_email(db, user.id, email_id, email, category, None)
        return

    # Extract structured data
    extracted = extract_order_data(
        subject=email["subject"],
        from_addr=email["from"],
        body=email["body_text"],
        category=category,
    )

    # Link/store to DB
    order = link_and_store(
        db=db,
        user_id=user.id,
        extracted=extracted,
        category=category,
        email_id=email_id,
    )

    # Log the processed email
    _log_email(db, user.id, email_id, email, category, order.id if order else None)


def _log_email(
    db: Session,
    user_id: int,
    gmail_message_id: str,
    email: dict,
    category: str,
    linked_order_id,
):
    """Write (or skip if duplicate) an EmailLog record."""
    # Check for duplicate (safety net – should already be filtered above)
    exists = (
        db.query(EmailLog)
        .filter(EmailLog.user_id == user_id, EmailLog.gmail_message_id == gmail_message_id)
        .first()
    )
    if exists:
        return

    log = EmailLog(
        user_id=user_id,
        gmail_message_id=gmail_message_id,
        subject=email.get("subject"),
        from_address=email.get("from"),
        received_at=email.get("date"),
        category=category,
        linked_order_id=linked_order_id,
    )
    db.add(log)
    db.commit()
