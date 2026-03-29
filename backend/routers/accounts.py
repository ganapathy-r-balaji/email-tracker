"""
routers/accounts.py – Connected Gmail account management.

GET    /api/accounts       – list connected Gmail accounts for the current user
DELETE /api/accounts/{id}  – disconnect a Gmail account (blocked if it's the last one)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import EmailLog, GmailAccount, User

router = APIRouter()


@router.get("/api/accounts")
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all Gmail accounts connected to the current user."""
    accounts = (
        db.query(GmailAccount)
        .filter(GmailAccount.user_id == current_user.id)
        .order_by(GmailAccount.created_at)
        .all()
    )
    return [
        {
            "id": a.id,
            "gmail_email": a.gmail_email,
            "created_at": a.created_at.isoformat(),
        }
        for a in accounts
    ]


@router.delete("/api/accounts/{account_id}")
def disconnect_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disconnect a Gmail account.
    Blocked if it would leave the user with zero connected accounts.
    Also nullifies the gmail_account_id on related EmailLog rows (keeps audit trail).
    """
    account = (
        db.query(GmailAccount)
        .filter(GmailAccount.id == account_id, GmailAccount.user_id == current_user.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    total = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).count()
    if total <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot disconnect your only Gmail account. Add another account first.",
        )

    # Nullify FK on email_log rows so audit history is preserved
    db.query(EmailLog).filter(EmailLog.gmail_account_id == account_id).update(
        {EmailLog.gmail_account_id: None}
    )

    db.delete(account)
    db.commit()
    return {"status": "disconnected", "gmail_email": account.gmail_email}
