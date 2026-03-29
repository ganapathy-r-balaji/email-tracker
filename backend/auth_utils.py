"""
auth_utils.py – Token encryption, session cookie management, and the
                get_current_user FastAPI dependency.
"""

import base64
import hashlib
import os
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from database import get_db

# ─── Fernet encryption ────────────────────────────────────────────────────────
# Derive a 32-byte Fernet key from SECRET_KEY (which can be any length string)
_SECRET_KEY = os.getenv("SECRET_KEY", "")
if not _SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

_fernet_key = base64.urlsafe_b64encode(
    hashlib.sha256(_SECRET_KEY.encode()).digest()
)
_fernet = Fernet(_fernet_key)


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token string for storage in the database."""
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted token from the database."""
    return _fernet.decrypt(encrypted.encode()).decode()


# ─── Signed session cookie ────────────────────────────────────────────────────
_serializer = URLSafeTimedSerializer(_SECRET_KEY)
_COOKIE_NAME = "session"
_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def create_session_cookie(user_id: int) -> str:
    """Return a signed, tamper-proof cookie value containing the user_id."""
    return _serializer.dumps({"user_id": user_id})


def decode_session_cookie(cookie_value: str) -> Optional[int]:
    """
    Decode and verify the session cookie.
    Returns user_id on success, None if invalid or expired.
    """
    try:
        data = _serializer.loads(cookie_value, max_age=_COOKIE_MAX_AGE_SECONDS)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


# ─── Google credential helpers ────────────────────────────────────────────────
def get_valid_google_credentials(account):
    """
    Build a google.oauth2.credentials.Credentials object from a GmailAccount's
    stored (encrypted) tokens. Auto-refreshes if expired.

    Accepts a GmailAccount model instance.
    The CALLER is responsible for persisting the refreshed token back to the DB.
    """
    import google.oauth2.credentials
    from google.auth.transport.requests import Request

    access_token = decrypt_token(account.access_token) if account.access_token else None
    refresh_token = decrypt_token(account.refresh_token) if account.refresh_token else None

    creds = google.oauth2.credentials.Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        expiry=account.token_expiry,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


# ─── FastAPI dependency ────────────────────────────────────────────────────────
def get_current_user(
    session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency that reads the signed session cookie and returns the
    authenticated User model. Raises 401 if the cookie is missing or invalid.
    """
    from models import User  # local import to avoid circular dependency

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = decode_session_cookie(session)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
