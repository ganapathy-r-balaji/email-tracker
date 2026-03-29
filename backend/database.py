"""
database.py – SQLAlchemy engine, session factory, and Base declaration.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")

# SQLite requires check_same_thread=False for FastAPI's threading model
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Enable WAL mode for SQLite so background sync and HTTP requests don't block each other
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_user_tokens_to_gmail_accounts(db):
    """
    One-time idempotent migration: copy tokens from the legacy users table columns
    into the new gmail_accounts table.

    Runs on every startup but is a no-op if GmailAccount rows already exist for
    users that have tokens. Safe to run repeatedly.
    """
    from models import GmailAccount, User

    users_with_tokens = (
        db.query(User).filter(User.gmail_refresh_token.isnot(None)).all()
    )
    migrated = 0
    for user in users_with_tokens:
        exists = (
            db.query(GmailAccount)
            .filter(
                GmailAccount.user_id == user.id,
                GmailAccount.gmail_email == user.email,
            )
            .first()
        )
        if not exists:
            account = GmailAccount(
                user_id=user.id,
                gmail_email=user.email,
                access_token=user.gmail_access_token,
                refresh_token=user.gmail_refresh_token,
                token_expiry=user.token_expiry,
            )
            db.add(account)
            migrated += 1

    if migrated:
        db.commit()
        print(f"✅ Migrated {migrated} user(s) tokens → gmail_accounts table.")


def init_db():
    """Create all tables and run migrations. Called on app startup."""
    # Import models here so they are registered on Base before create_all
    from models import GmailAccount, User, Order, Item, Shipment, EmailLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created (or already exist).")

    # Run token migration so existing users get a GmailAccount row
    db = SessionLocal()
    try:
        _migrate_user_tokens_to_gmail_accounts(db)
    finally:
        db.close()
