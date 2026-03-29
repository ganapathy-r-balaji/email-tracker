"""
routers/sync.py – Email sync orchestration.

POST /api/sync       – trigger a manual sync (runs in background)
GET  /api/sync/status – get last_sync_at for the current user
"""

import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import encrypt_token, get_current_user, get_valid_google_credentials
from database import SessionLocal, get_db
from models import EmailCategory, EmailLog, GmailAccount, User
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
    db: Session = Depends(get_db),
):
    accounts = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="No Gmail accounts connected. Please connect a Gmail account first.",
        )

    background_tasks.add_task(run_sync, current_user.id)
    count = len(accounts)
    label = "account" if count == 1 else "accounts"
    return {
        "status": "sync_started",
        "message": f"Syncing {count} Gmail {label} in the background.",
    }


# ─── Force re-sync (clears existing logs and re-processes) ────────────────────
@router.post("/api/sync/reset")
def reset_and_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=400, detail="No Gmail accounts connected.")

    # Clear all email logs so they get reprocessed
    db.query(EmailLog).filter(EmailLog.user_id == current_user.id).delete()
    db.commit()

    background_tasks.add_task(run_sync, current_user.id)
    return {"status": "reset_started", "message": "Email logs cleared. Re-syncing all emails."}


# ─── Sync status ──────────────────────────────────────────────────────────────
@router.get("/api/sync/status")
def sync_status(current_user: User = Depends(get_current_user)):
    return {
        "last_sync_at": current_user.last_sync_at.isoformat() if current_user.last_sync_at else None,
    }


# ─── Core sync pipeline ───────────────────────────────────────────────────────
def run_sync(user_id: int):
    """
    Sync all connected Gmail accounts for a user.
    Each account is processed independently; errors in one don't stop others.
    """
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"[Sync] User {user_id} not found, skipping.")
            return

        accounts = db.query(GmailAccount).filter(GmailAccount.user_id == user_id).all()
        if not accounts:
            print(f"[Sync] No Gmail accounts for user {user_id}, skipping.")
            return

        print(f"[Sync] Starting sync for {user.email} ({len(accounts)} account(s))")

        for account in accounts:
            try:
                _sync_single_account(db, user, account)
            except Exception as exc:
                print(f"[Sync] Error syncing account {account.gmail_email}: {exc}")

        user.last_sync_at = datetime.utcnow()
        db.commit()
        print(f"[Sync] Finished sync for {user.email}.")

    except Exception as exc:
        print(f"[Sync] Unhandled error for user {user_id}: {exc}")
    finally:
        db.close()


def _sync_single_account(db: Session, user: User, account: GmailAccount):
    """Sync one Gmail account: fetch → classify → extract → store."""
    print(f"[Sync]   → {account.gmail_email}")

    # Get valid credentials (auto-refresh if expired)
    try:
        credentials = get_valid_google_credentials(account)
    except Exception as exc:
        print(f"[Sync] Failed to get credentials for {account.gmail_email}: {exc}")
        return

    # Persist refreshed access token
    if credentials.token:
        account.access_token = encrypt_token(credentials.token)
        account.token_expiry = credentials.expiry
        db.commit()

    # Fetch email IDs
    gmail = build_gmail_service(credentials)
    all_ids = search_order_emails(gmail, max_results=MAX_RESULTS)
    print(f"[Sync]     Found {len(all_ids)} candidate emails.")

    # Filter already-processed (dedup per user across all accounts)
    existing_ids = {
        row[0]
        for row in db.query(EmailLog.gmail_message_id)
        .filter(EmailLog.user_id == user.id)
        .all()
    }
    new_ids = [eid for eid in all_ids if eid not in existing_ids]
    print(f"[Sync]     {len(new_ids)} new to process.")

    processed = 0
    for email_id in new_ids:
        try:
            _process_single_email(db, user, account, gmail, email_id)
            processed += 1
        except Exception as exc:
            print(f"[Sync] Error processing email {email_id}: {exc}")
            _log_email(db, user.id, account.id, email_id, {}, "error", None)

    print(f"[Sync]     Processed {processed}/{len(new_ids)} emails for {account.gmail_email}.")


def _process_single_email(
    db: Session, user: User, account: GmailAccount, gmail, email_id: str
):
    """Fetch, classify, extract, link, and log a single email."""
    email = get_email_details(gmail, email_id)

    classification = classify_email(
        subject=email["subject"],
        from_addr=email["from"],
        body=email["body_text"],
    )
    category = classification.get("category", EmailCategory.IRRELEVANT)

    if category == EmailCategory.IRRELEVANT:
        _log_email(db, user.id, account.id, email_id, email, category, None)
        return

    extracted = extract_order_data(
        subject=email["subject"],
        from_addr=email["from"],
        body=email["body_text"],
        category=category,
        email_date=email.get("date"),
    )

    # Fallback: if Claude couldn't extract an order_date, use the email's received date
    if not extracted.get("order_date") and email.get("date"):
        extracted["order_date"] = email["date"].strftime("%Y-%m-%d")

    order = link_and_store(
        db=db,
        user_id=user.id,
        extracted=extracted,
        category=category,
        email_id=email_id,
    )

    _log_email(db, user.id, account.id, email_id, email, category, order.id if order else None)


def _log_email(
    db: Session,
    user_id: int,
    gmail_account_id: int,
    gmail_message_id: str,
    email: dict,
    category: str,
    linked_order_id,
):
    """Write an EmailLog record (skip silently if duplicate)."""
    exists = (
        db.query(EmailLog)
        .filter(EmailLog.user_id == user_id, EmailLog.gmail_message_id == gmail_message_id)
        .first()
    )
    if exists:
        return

    log = EmailLog(
        user_id=user_id,
        gmail_account_id=gmail_account_id,
        gmail_message_id=gmail_message_id,
        subject=email.get("subject"),
        from_address=email.get("from"),
        received_at=email.get("date"),
        category=category,
        linked_order_id=linked_order_id,
    )
    db.add(log)
    db.commit()
