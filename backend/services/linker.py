"""
services/linker.py – Links extracted email data to existing Order/Shipment records.

Matching strategy (in priority order):
  1. Exact vendor_order_id match (case-insensitive)
  2. Tracking number match against existing shipments
  3. Vendor name + order date proximity (within 90 days)

Creates new records if no match is found.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import EmailCategory, Item, Order, OrderStatus, Shipment


def link_and_store(
    db: Session,
    user_id: int,
    extracted: dict,
    category: str,
    email_id: str,
) -> Optional[Order]:
    """
    Given extracted email data and its category, find or create the
    corresponding Order and persist all related records.

    Returns the Order object (new or existing), or None if irrelevant.
    """
    if category == EmailCategory.IRRELEVANT:
        return None

    if category == EmailCategory.ORDER_CONFIRMATION:
        return _handle_order_confirmation(db, user_id, extracted, email_id)
    elif category == EmailCategory.SHIPPING_UPDATE:
        return _handle_shipping_update(db, user_id, extracted, email_id)
    elif category == EmailCategory.DELIVERY_CONFIRMATION:
        return _handle_delivery_confirmation(db, user_id, extracted)

    return None


# ─── Handlers ─────────────────────────────────────────────────────────────────

def _handle_order_confirmation(
    db: Session, user_id: int, extracted: dict, email_id: str
) -> Order:
    """Create a new order (or update an existing one if we've seen this order_id before)."""
    vendor_order_id = _clean(extracted.get("vendor_order_id"))
    vendor = _clean(extracted.get("vendor"))

    # Check for existing order by vendor_order_id
    existing = None
    if vendor_order_id:
        existing = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.vendor_order_id.ilike(vendor_order_id),
            )
            .first()
        )

    if existing:
        # Update status if it's still at "unknown"
        if existing.status == OrderStatus.UNKNOWN:
            existing.status = OrderStatus.ORDERED
        db.commit()
        return existing

    # Create new order
    order = Order(
        user_id=user_id,
        vendor_order_id=vendor_order_id,
        vendor=vendor,
        order_date=_parse_date(extracted.get("order_date")),
        total_price=_safe_float(extracted.get("total_price")),
        currency=_clean(extracted.get("currency")) or "USD",
        status=OrderStatus.ORDERED,
        confirmation_email_id=email_id,
    )
    db.add(order)
    db.flush()  # Get order.id without committing

    # Add line items
    for item_data in extracted.get("items", []):
        name = _clean(item_data.get("name"))
        if not name:
            continue
        item = Item(
            order_id=order.id,
            name=name,
            quantity=int(item_data.get("quantity") or 1),
            unit_price=_safe_float(item_data.get("unit_price")),
            category=_clean(item_data.get("category")),
        )
        db.add(item)

    # Add shipment info if present in the confirmation email
    tracking = _clean(extracted.get("tracking_number"))
    if tracking:
        shipment = Shipment(
            order_id=order.id,
            tracking_number=tracking,
            carrier=_clean(extracted.get("carrier")),
            estimated_delivery=_parse_date(extracted.get("estimated_delivery")),
            tracking_url=_clean(extracted.get("tracking_url")),
        )
        db.add(shipment)

    db.commit()
    db.refresh(order)
    return order


def _handle_shipping_update(
    db: Session, user_id: int, extracted: dict, email_id: str
) -> Optional[Order]:
    """Find the matching order and upsert a Shipment record."""
    order = _find_matching_order(db, user_id, extracted)

    if order is None:
        # No matching order found – create a placeholder order so we don't lose tracking info
        order = Order(
            user_id=user_id,
            vendor_order_id=_clean(extracted.get("vendor_order_id")),
            vendor=_clean(extracted.get("vendor")),
            order_date=_parse_date(extracted.get("order_date")),
            status=OrderStatus.SHIPPED,
        )
        db.add(order)
        db.flush()

    # Update order status
    if order.status in (OrderStatus.ORDERED, OrderStatus.UNKNOWN):
        order.status = OrderStatus.SHIPPED

    # Upsert shipment
    tracking = _clean(extracted.get("tracking_number"))
    existing_shipment = None
    if tracking:
        existing_shipment = (
            db.query(Shipment)
            .filter(Shipment.order_id == order.id, Shipment.tracking_number == tracking)
            .first()
        )

    if existing_shipment:
        # Update with latest info
        if extracted.get("estimated_delivery"):
            existing_shipment.estimated_delivery = _parse_date(extracted.get("estimated_delivery"))
        if extracted.get("carrier"):
            existing_shipment.carrier = _clean(extracted.get("carrier"))
        if extracted.get("tracking_url"):
            existing_shipment.tracking_url = _clean(extracted.get("tracking_url"))
    else:
        shipment = Shipment(
            order_id=order.id,
            tracking_number=tracking,
            carrier=_clean(extracted.get("carrier")),
            shipped_date=_parse_date(extracted.get("order_date")),
            estimated_delivery=_parse_date(extracted.get("estimated_delivery")),
            tracking_url=_clean(extracted.get("tracking_url")),
        )
        db.add(shipment)

    db.commit()
    db.refresh(order)
    return order


def _handle_delivery_confirmation(
    db: Session, user_id: int, extracted: dict
) -> Optional[Order]:
    """Mark the order as delivered and record the actual delivery date."""
    order = _find_matching_order(db, user_id, extracted)
    if order is None:
        return None

    order.status = OrderStatus.DELIVERED

    # Find the most recent shipment and set its actual_delivery
    if order.shipments:
        latest_shipment = sorted(order.shipments, key=lambda s: s.created_at, reverse=True)[0]
        latest_shipment.actual_delivery = datetime.utcnow()

    db.commit()
    db.refresh(order)
    return order


# ─── Matching logic ───────────────────────────────────────────────────────────

def _find_matching_order(db: Session, user_id: int, extracted: dict) -> Optional[Order]:
    """
    Try to match an email to an existing order using three strategies:
      1. Exact vendor_order_id (case-insensitive)
      2. Tracking number on any of the user's shipments
      3. Vendor name + order date within 90-day window
    """
    # Strategy 1: vendor_order_id
    vendor_order_id = _clean(extracted.get("vendor_order_id"))
    if vendor_order_id:
        match = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.vendor_order_id.ilike(vendor_order_id),
            )
            .first()
        )
        if match:
            return match

    # Strategy 2: tracking number
    tracking = _clean(extracted.get("tracking_number"))
    if tracking:
        shipment = (
            db.query(Shipment)
            .join(Order)
            .filter(Order.user_id == user_id, Shipment.tracking_number == tracking)
            .first()
        )
        if shipment:
            return shipment.order

    # Strategy 3: vendor + date proximity (within 90 days)
    vendor = _clean(extracted.get("vendor"))
    order_date = _parse_date(extracted.get("order_date"))
    if vendor and order_date:
        window_start = order_date - timedelta(days=90)
        window_end = order_date + timedelta(days=90)
        match = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.vendor.ilike(f"%{vendor}%"),
                Order.order_date.between(window_start, window_end),
            )
            .first()
        )
        if match:
            return match

    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean(val) -> Optional[str]:
    """Return stripped string or None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _safe_float(val) -> Optional[float]:
    """Convert to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> Optional[datetime]:
    """Parse an ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) to datetime."""
    if not val or not isinstance(val, str):
        return None
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(val)
    except Exception:
        return None
