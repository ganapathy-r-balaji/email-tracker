"""
main.py – FastAPI application entry point.

Startup sequence:
  1. Load .env
  2. Initialize database (create tables)
  3. Start APScheduler background sync
  4. Mount routers
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Must be first – other modules read env vars on import

# Allow OAuth over plain HTTP on localhost (development only).
# google-auth-oauthlib refuses non-HTTPS by default; this env var disables that check.
# NEVER set this in production – always run behind HTTPS there.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from database import init_db
from routers.accounts import router as accounts_router
from routers.auth import router as auth_router
from routers.orders import router as orders_router
from routers.spending import router as spending_router
from routers.sync import router as sync_router

app = FastAPI(
    title="AI Email Package Tracker",
    description="Tracks orders and shipments from your Gmail inbox using Claude AI.",
    version="1.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# IMPORTANT: allow_credentials=True REQUIRES a specific origin list, never "*"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Session middleware (used for OAuth state storage in Phase 4) ──────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "fallback-dev-secret"),
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(orders_router)
app.include_router(spending_router)
app.include_router(sync_router)


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    from scheduler import start_scheduler
    start_scheduler()
    print("🚀 Email Tracker API is running.")


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
