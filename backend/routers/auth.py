"""
routers/auth.py – Gmail OAuth2 flow endpoints.

Supports three flows:
  1. New login    – no session cookie → create User + first GmailAccount
  2. Re-login     – session exists, no action=add → refresh existing GmailAccount tokens
  3. Add account  – GET /auth/google?action=add while logged in → add second GmailAccount

Endpoints:
  GET /auth/google           – Redirect user to Google consent screen
  GET /auth/google/callback  – Handle OAuth callback
  GET /auth/logout           – Clear session cookie
  GET /api/me                – Return current user info (protected)
"""

import base64
import hashlib
import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from auth_utils import (
    create_session_cookie,
    decode_session_cookie,
    encrypt_token,
    get_current_user,
)
from database import get_db
from models import GmailAccount, User

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
def google_login(
    request: Request,
    response: Response,
    action: str = Query(default=""),  # "add" → link a new Gmail to existing user
):
    """
    Redirect the user to Google's OAuth consent screen.
    Pass ?action=add when the user wants to add a second Gmail account.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth credentials are not configured.",
        )

    # ── PKCE ─────────────────────────────────────────────────────────────────
    code_verifier = secrets.token_urlsafe(96)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )

    is_production = not GOOGLE_REDIRECT_URI.startswith("http://localhost")

    redirect = RedirectResponse(url=authorization_url)
    redirect.set_cookie(key="oauth_state", value=state, httponly=True, max_age=300,
                        samesite="none" if is_production else "lax", secure=is_production)
    redirect.set_cookie(key="oauth_code_verifier", value=code_verifier, httponly=True, max_age=300,
                        samesite="none" if is_production else "lax", secure=is_production)

    # If adding a second account, remember which user to link it to
    if action == "add":
        session_cookie = request.cookies.get("session")
        if session_cookie:
            from auth_utils import decode_session_cookie as _decode
            linking_user_id = _decode(session_cookie)
            if linking_user_id:
                redirect.set_cookie(
                    key="oauth_linking_user_id",
                    value=str(linking_user_id),
                    httponly=True,
                    max_age=300,
                    samesite="none" if is_production else "lax",
                    secure=is_production,
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
    Handle the redirect back from Google.
    Determines which flow this is (new login / re-login / add account)
    from the oauth_linking_user_id cookie.
    """
    # ── User denied consent ───────────────────────────────────────────────────
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=access_denied")

    # ── CSRF state check ──────────────────────────────────────────────────────
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=state_mismatch")

    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=no_code")

    # ── Token exchange (with PKCE verifier) ───────────────────────────────────
    code_verifier = request.cookies.get("oauth_code_verifier")
    try:
        flow = _build_flow()
        flow.fetch_token(code=code, code_verifier=code_verifier)
        credentials: Credentials = flow.credentials
    except Exception as exc:
        print(f"Token exchange error: {exc}")
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=token_exchange_failed")

    # ── Get Google user info ──────────────────────────────────────────────────
    try:
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        gmail_email = user_info.get("email", "").lower()
    except Exception as exc:
        print(f"Failed to fetch user info: {exc}")
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=userinfo_failed")

    if not gmail_email:
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=no_email")

    # ── Determine flow: add-account vs new/re-login ───────────────────────────
    linking_user_id_str = request.cookies.get("oauth_linking_user_id")
    linking_user_id = int(linking_user_id_str) if linking_user_id_str and linking_user_id_str.isdigit() else None

    if linking_user_id:
        # ── Add account flow: link new Gmail to existing user ─────────────────
        user = db.query(User).filter(User.id == linking_user_id).first()
        if not user:
            return RedirectResponse(url=f"{FRONTEND_URL}/?error=user_not_found")
        redirect_url = f"{FRONTEND_URL}/dashboard?account_added=true"
    else:
        # ── New login / re-login flow: user identified by gmail_email ─────────
        # The primary User record uses the first Gmail address as identity
        user = db.query(User).filter(User.email == gmail_email).first()
        if user is None:
            user = User(email=gmail_email)
            db.add(user)
            db.flush()  # get user.id without committing
        redirect_url = f"{FRONTEND_URL}/dashboard"

    # ── Upsert GmailAccount ───────────────────────────────────────────────────
    account = (
        db.query(GmailAccount)
        .filter(GmailAccount.user_id == user.id, GmailAccount.gmail_email == gmail_email)
        .first()
    )
    if account is None:
        account = GmailAccount(user_id=user.id, gmail_email=gmail_email)
        db.add(account)

    account.access_token = encrypt_token(credentials.token) if credentials.token else account.access_token
    account.refresh_token = encrypt_token(credentials.refresh_token) if credentials.refresh_token else account.refresh_token
    account.token_expiry = credentials.expiry

    db.commit()
    db.refresh(user)

    # ── Set session cookie + redirect ─────────────────────────────────────────
    session_value = create_session_cookie(user.id)
    redirect = RedirectResponse(url=redirect_url)
    redirect.set_cookie(
        key="session",
        value=session_value,
        httponly=True,
        max_age=60 * 60 * 24 * 30,
        samesite="none" if is_production else "lax",
        secure=is_production,
    )
    redirect.delete_cookie("oauth_state")
    redirect.delete_cookie("oauth_code_verifier")
    redirect.delete_cookie("oauth_linking_user_id")
    return redirect


# ─── Logout ───────────────────────────────────────────────────────────────────
@router.get("/auth/logout")
def logout():
    response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("session")
    return response


# ─── Current user info ────────────────────────────────────────────────────────
@router.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "last_sync_at": current_user.last_sync_at.isoformat() if current_user.last_sync_at else None,
        "created_at": current_user.created_at.isoformat(),
    }
