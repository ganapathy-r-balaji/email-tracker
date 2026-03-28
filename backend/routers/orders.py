"""
routers/orders.py – Order and stats endpoints.

Endpoints:
  GET /api/orders            – paginated list of orders with items + latest shipment
  GET /api/orders/{order_id} – full order detail (all items + all shipments)
  GET /api/stats/summary     – summary stats for the dashboard
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from auth_utils import get_current_user
from database import get_db
from models import Item, Order, OrderStatus, Shipment, User

router = APIRouter()


# ─── Helpers: serializers ─────────────────────────────────────────────────────

def _serialize_item(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "category": item.category,
    }


def _serialize_shipment(shipment: Shipment) -> dict:
    return {
        "id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "shipped_date": shipment.shipped_date.isoformat() if shipment.shipped_date else None,
        "estimated_delivery": shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None,
        "actual_delivery": shipment.actual_delivery.isoformat() if shipment.actual_delivery else None,
        "tracking_url": shipment.tracking_url,
    }


def _serialize_order(order: Order, include_all_shipments: bool = False) -> dict:
    items = [_serialize_item(i) for i in order.items]

    if include_all_shipments:
        shipments = [_serialize_shipment(s) for s in order.shipments]
        latest_shipment = shipments[0] if shipments else None
    else:
        # Only return the most recent shipment for list view
        sorted_shipments = sorted(order.shipments, key=lambda s: s.created_at, reverse=True)
        latest_shipment = _serialize_shipment(sorted_shipments[0]) if sorted_shipments else None
        shipments = [latest_shipment] if latest_shipment else []

    return {
        "id": order.id,
        "vendor_order_id": order.vendor_order_id,
        "vendor": order.vendor,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "total_price": order.total_price,
        "currency": order.currency,
        "status": order.status,
        "items": items,
        "item_count": len(items),
        "shipments": shipments if include_all_shipments else None,
        "latest_shipment": latest_shipment,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


# ─── Orders list ─────────────────────────────────────────────────────────────
@router.get("/api/orders")
def list_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    vendor: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a paginated list of orders for the current user.
    Each order includes its items and the most recent shipment.

    Query params:
      page     – page number (default 1)
      per_page – results per page (default 20, max 100)
      status   – filter by status (ordered/shipped/delivered/unknown)
      vendor   – filter by vendor name (case-insensitive contains)
    """
    query = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .options(selectinload(Order.items), selectinload(Order.shipments))
    )

    if status:
        query = query.filter(Order.status == status)
    if vendor:
        query = query.filter(Order.vendor.ilike(f"%{vendor}%"))

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "orders": [_serialize_order(o) for o in orders],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


# ─── Order detail ─────────────────────────────────────────────────────────────
@router.get("/api/orders/{order_id}")
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return full detail for a single order, including all items and all shipments."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .options(selectinload(Order.items), selectinload(Order.shipments))
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return _serialize_order(order, include_all_shipments=True)


# ─── Stats summary ────────────────────────────────────────────────────────────
@router.get("/api/stats/summary")
def stats_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return summary statistics for the dashboard header.

    Returns:
      total_orders      – total number of tracked orders
      pending_delivery  – orders with status ordered or shipped
      delivered         – orders with status delivered
      last_sync_at      – ISO datetime of last email sync
      top_vendors       – top 5 vendors by order count
    """
    user_orders = db.query(Order).filter(Order.user_id == current_user.id)

    total = user_orders.count()
    pending = user_orders.filter(Order.status.in_([OrderStatus.ORDERED, OrderStatus.SHIPPED])).count()
    delivered = user_orders.filter(Order.status == OrderStatus.DELIVERED).count()

    # Top 5 vendors
    vendor_counts = (
        db.query(Order.vendor, func.count(Order.id).label("count"))
        .filter(Order.user_id == current_user.id, Order.vendor.isnot(None))
        .group_by(Order.vendor)
        .order_by(func.count(Order.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_orders": total,
        "pending_delivery": pending,
        "delivered": delivered,
        "last_sync_at": current_user.last_sync_at.isoformat() if current_user.last_sync_at else None,
        "top_vendors": [{"name": v, "count": c} for v, c in vendor_counts],
    }
