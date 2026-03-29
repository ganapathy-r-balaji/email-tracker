"""
models.py – SQLAlchemy ORM models.

Tables:
  users           – authenticated users (one per person, identified by primary Gmail)
  gmail_accounts  – connected Gmail inboxes (many per user)
  orders          – individual orders extracted from emails
  items           – line items within an order
  shipments       – shipping/tracking info linked to an order
  email_log       – audit log of every processed Gmail message
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ─── Order status enum (stored as string) ────────────────────────────────────
class OrderStatus:
    ORDERED = "ordered"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    UNKNOWN = "unknown"


# ─── Email category enum ──────────────────────────────────────────────────────
class EmailCategory:
    ORDER_CONFIRMATION = "order_confirmation"
    SHIPPING_UPDATE = "shipping_update"
    DELIVERY_CONFIRMATION = "delivery_confirmation"
    IRRELEVANT = "irrelevant"


# ─── Users ───────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Legacy single-account token columns – kept for SQLite compat (cannot drop columns).
    # Tokens for all accounts now live in GmailAccount. A startup migration copies
    # existing values here into gmail_accounts automatically.
    gmail_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gmail_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    gmail_accounts: Mapped[List["GmailAccount"]] = relationship(
        "GmailAccount", back_populates="user", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )
    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ─── Gmail Accounts ───────────────────────────────────────────────────────────
class GmailAccount(Base):
    """One row per connected Gmail inbox per user."""

    __tablename__ = "gmail_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    gmail_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Fernet-encrypted OAuth tokens
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="gmail_accounts")
    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="gmail_account"
    )

    # Each Gmail address can only be connected once per user
    __table_args__ = (
        UniqueConstraint("user_id", "gmail_email", name="uq_user_gmail_email"),
    )

    def __repr__(self) -> str:
        return f"<GmailAccount id={self.id} email={self.gmail_email} user_id={self.user_id}>"


# ─── Orders ──────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    vendor_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    order_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="USD")

    status: Mapped[str] = mapped_column(String(50), default=OrderStatus.UNKNOWN, nullable=False)

    confirmation_email_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="orders")
    items: Mapped[List["Item"]] = relationship(
        "Item", back_populates="order", cascade="all, delete-orphan"
    )
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment", back_populates="order", cascade="all, delete-orphan"
    )
    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="linked_order"
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} vendor={self.vendor} status={self.status}>"


# ─── Items ───────────────────────────────────────────────────────────────────
class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<Item id={self.id} name={self.name!r} qty={self.quantity}>"


# ─── Shipments ───────────────────────────────────────────────────────────────
class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    tracking_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    carrier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    shipped_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    estimated_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    tracking_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="shipments")

    def __repr__(self) -> str:
        return f"<Shipment id={self.id} tracking={self.tracking_number} carrier={self.carrier}>"


# ─── Email Log ───────────────────────────────────────────────────────────────
class EmailLog(Base):
    __tablename__ = "email_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Which Gmail account this email came from (nullable for legacy rows)
    gmail_account_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("gmail_accounts.id"), nullable=True, index=True
    )

    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    from_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    linked_order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="email_logs")
    gmail_account: Mapped[Optional["GmailAccount"]] = relationship(
        "GmailAccount", back_populates="email_logs"
    )
    linked_order: Mapped[Optional["Order"]] = relationship("Order", back_populates="email_logs")

    __table_args__ = (
        UniqueConstraint("user_id", "gmail_message_id", name="uq_user_message"),
    )

    def __repr__(self) -> str:
        return f"<EmailLog id={self.id} msg={self.gmail_message_id} cat={self.category}>"
