"""
routers/auth.py – Gmail OAuth2 flow endpoints.

Endpoints:
  GET /auth/google           – Redirect user to Google consent screen
  GET /auth/google/callback  – Handle OAuth callback, create/update user, set session cookie
  GET /auth/logout           – Clear session cookie and redirect to frontend
  GET /api/me                – Return current user info (protected)
"""

import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from auth_utils import (
    create_session_cookie,
    decode_session_cookie,
    decrypt_token,
    encrypt_token,
    get_current_user,
)
from database import get_db
from models import User

router = APIRouter()

# ─── Constants ────────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [GOOGLE_REDIRECT_URI],
    }
}


def _build_flow() -> Flow:
    flow = Flow.from_client_config(_CLIENT_CONFIG, scopes=GMAIL_SCOPES)
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow


# ─── Initiate OAuth ───────────────────────────────────────────────────────────
@router.get("/auth/google")
def google_login(response: Response):
    """
    Redirect the user to Google's OAuth consent screen.
    A random state token is set in a short-lived cookie for CSRF protection.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth credentials are not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )

    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",           # Request a refresh token
        include_granted_scopes="true",
        prompt="consent",                # Always show consent to ensure refresh_token is returned
    )

    redirect = RedirectResponse(url=authorization_url)
    # Store state in a short-lived signed cookie (5 min) for CSRF verification
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=300,
        samesite="lax",
    )
    return redirect


# ─── OAuth Callback ───────────────────────────────────────────────────────────
@router.get("/auth/google/callback")
def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    """
    Handle the redirect back from Google after the user grants/denies consent.
    On success: create/update user, set session cookie, redirect to dashboard.
    On failure: redirect to frontend with an error message.
    """
    # ── Handle user denying consent ──────────────────────────────────────────
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=access_denied")

    # ── CSRF state validation ─────────────────────────────────────────────────
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=state_mismatch")

    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=no_code")

    # ── Exchange authorization code for tokens ────────────────────────────────
    try:
        flow = _build_flow()
        flow.fetch_token(code=code)
        credentials: Credentials = flow.credentials
    except Exception as exc:
        print(f"Token exchange error: {exc}")
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=token_exchange_failed")

    # ── Get the user's email address from Google ──────────────────────────────
    try:
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        email = user_info.get("email", "").lower()
    except Exception as exc:
        print(f"Failed to fetch user info: {exc}")
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=userinfo_failed")

    if not email:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=no_email")

    # ── Upsert user in DB ─────────────────────────────────────────────────────
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email)
        db.add(user)

    user.gmail_access_token = encrypt_token(credentials.token) if credentials.token else None
    user.gmail_refresh_token = encrypt_token(credentials.refresh_token) if credentials.refresh_token else user.gmail_refresh_token
    user.token_expiry = credentials.expiry  # UTC datetime or None

    db.commit()
    db.refresh(user)

    # ── Set signed session cookie ─────────────────────────────────────────────
    session_value = create_session_cookie(user.id)

    redirect = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    redirect.set_cookie(
        key="session",
        value=session_value,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 days
        samesite="lax",
        secure=False,   # Set to True in production (HTTPS only)
    )
    # Clear the OAuth state cookie
    redirect.delete_cookie("oauth_state")
    return redirect


# ─── Logout ───────────────────────────────────────────────────────────────────
@router.get("/auth/logout")
def logout():
    """Clear the session cookie and redirect to the landing page."""
    response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("session")
    return response


# ─── Current user info ────────────────────────────────────────────────────────
@router.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile information."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "last_sync_at": current_user.last_sync_at.isoformat() if current_user.last_sync_at else None,
        "created_at": current_user.created_at.isoformat(),
    }
