"""
routers/spending.py – Spending analytics endpoint.

GET /api/stats/spending?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

Returns six breakdowns for the given date range:
  1. by_year_month    – total spend per calendar month (time series)
  2. by_month_of_year – total spend aggregated per month name across years (Jan–Dec)
  3. by_week_of_month – total spend by week position within a month (weeks 1–5)
  4. by_week_of_year  – total spend by ISO week number (weeks 1–53)
  5. categories       – total spend by item category (from items table)
  6. top_vendors      – top 10 vendors by total spend

All monetary values are in the user's primary currency only.
Orders with null total_price or null order_date are excluded.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, cast, Integer
from sqlalchemy.orm import Session

from auth_utils import get_current_user
from database import get_db
from models import Item, Order, User

router = APIRouter()

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ─── Defaults ─────────────────────────────────────────────────────────────────
def _default_start() -> str:
    """12 months ago from today."""
    today = date.today()
    start = today.replace(year=today.year - 1) if today.month != 2 or today.day != 29 else \
        today.replace(year=today.year - 1, day=28)
    return start.isoformat()


def _default_end() -> str:
    return date.today().isoformat()


# ─── Primary currency helper ──────────────────────────────────────────────────
def _primary_currency(db: Session, user_id: int, start: datetime, end: datetime) -> str:
    row = (
        db.query(Order.currency, func.count(Order.id).label("cnt"))
        .filter(
            Order.user_id == user_id,
            Order.currency.isnot(None),
            Order.order_date >= start,
            Order.order_date <= end,
        )
        .group_by(Order.currency)
        .order_by(func.count(Order.id).desc())
        .first()
    )
    return row[0] if row else "USD"


# ─── Endpoint ─────────────────────────────────────────────────────────────────
@router.get("/api/stats/spending")
def spending_stats(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return six spending breakdown datasets for the given date range.

    Params:
      start_date – ISO date string (default: 12 months ago)
      end_date   – ISO date string (default: today)
    """
    start_str = start_date or _default_start()
    end_str = end_date or _default_end()

    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format.")

    uid = current_user.id
    currency = _primary_currency(db, uid, start_dt, end_dt)

    # Base filter shared by order-level queries
    base = (
        Order.user_id == uid,
        Order.total_price.isnot(None),
        Order.order_date.isnot(None),
        Order.currency == currency,
        Order.order_date >= start_dt,
        Order.order_date <= end_dt,
    )

    # ── 1. By year-month ──────────────────────────────────────────────────────
    ym_rows = (
        db.query(
            func.strftime("%Y", Order.order_date).label("yr"),
            func.strftime("%m", Order.order_date).label("mo"),
            func.sum(Order.total_price).label("total"),
            func.count(Order.id).label("cnt"),
        )
        .filter(*base)
        .group_by(
            func.strftime("%Y", Order.order_date),
            func.strftime("%m", Order.order_date),
        )
        .order_by("yr", "mo")
        .all()
    )

    by_year_month = [
        {
            "year": int(r.yr),
            "month": int(r.mo),
            "label": f"{MONTH_NAMES[int(r.mo) - 1]} '{r.yr[2:]}",
            "total": round(r.total or 0, 2),
            "order_count": r.cnt,
        }
        for r in ym_rows
    ]

    # ── 2. By month of year (Jan–Dec aggregate across all years in range) ─────
    moy_rows = (
        db.query(
            func.strftime("%m", Order.order_date).label("mo"),
            func.sum(Order.total_price).label("total"),
            func.count(Order.id).label("cnt"),
        )
        .filter(*base)
        .group_by(func.strftime("%m", Order.order_date))
        .order_by("mo")
        .all()
    )

    moy_map = {int(r.mo): (round(r.total or 0, 2), r.cnt) for r in moy_rows}
    by_month_of_year = [
        {
            "month": m,
            "label": MONTH_NAMES[m - 1],
            "total": moy_map.get(m, (0.0, 0))[0],
            "order_count": moy_map.get(m, (0.0, 0))[1],
        }
        for m in range(1, 13)
    ]

    # ── 3. By week of month (1–5) ─────────────────────────────────────────────
    # SQLite: week_of_month = ((day - 1) / 7) + 1
    day_expr = cast(func.strftime("%d", Order.order_date), Integer)
    week_of_month_expr = (day_expr - 1) / 7 + 1

    wom_rows = (
        db.query(
            week_of_month_expr.label("wom"),
            func.sum(Order.total_price).label("total"),
            func.count(Order.id).label("cnt"),
        )
        .filter(*base)
        .group_by(week_of_month_expr)
        .order_by(week_of_month_expr)
        .all()
    )

    wom_map = {int(r.wom): (round(r.total or 0, 2), r.cnt) for r in wom_rows}
    by_week_of_month = [
        {
            "week": w,
            "label": f"Week {w}",
            "total": wom_map.get(w, (0.0, 0))[0],
            "order_count": wom_map.get(w, (0.0, 0))[1],
        }
        for w in range(1, 6)
    ]

    # ── 4. By week of year (ISO week 00–53) ───────────────────────────────────
    woy_rows = (
        db.query(
            func.strftime("%Y", Order.order_date).label("yr"),
            func.strftime("%W", Order.order_date).label("wk"),
            func.sum(Order.total_price).label("total"),
            func.count(Order.id).label("cnt"),
        )
        .filter(*base)
        .group_by(
            func.strftime("%Y", Order.order_date),
            func.strftime("%W", Order.order_date),
        )
        .order_by("yr", "wk")
        .all()
    )

    by_week_of_year = [
        {
            "year": int(r.yr),
            "week": int(r.wk),
            "label": f"W{int(r.wk)} '{r.yr[2:]}",
            "total": round(r.total or 0, 2),
            "order_count": r.cnt,
        }
        for r in woy_rows
    ]

    # ── 5. By product category (from items table) ─────────────────────────────
    cat_rows = (
        db.query(
            func.coalesce(Item.category, "Uncategorized").label("cat"),
            func.sum(Item.unit_price * Item.quantity).label("total"),
            func.count(Item.id.distinct()).label("cnt"),
        )
        .join(Order, Order.id == Item.order_id)
        .filter(
            Order.user_id == uid,
            Item.unit_price.isnot(None),
            Order.order_date.isnot(None),
            Order.order_date >= start_dt,
            Order.order_date <= end_dt,
        )
        .group_by(func.coalesce(Item.category, "Uncategorized"))
        .order_by(func.sum(Item.unit_price * Item.quantity).desc())
        .all()
    )

    categories = [
        {
            "category": r.cat,
            "total": round(r.total or 0, 2),
            "order_count": r.cnt,
        }
        for r in cat_rows
    ]

    # ── 6. Top vendors ────────────────────────────────────────────────────────
    vendor_rows = (
        db.query(
            func.coalesce(Order.vendor, "Unknown").label("vendor"),
            func.sum(Order.total_price).label("total"),
            func.count(Order.id).label("cnt"),
        )
        .filter(*base)
        .group_by(func.coalesce(Order.vendor, "Unknown"))
        .order_by(func.sum(Order.total_price).desc())
        .limit(10)
        .all()
    )

    top_vendors = [
        {
            "vendor": r.vendor,
            "total_spent": round(r.total or 0, 2),
            "order_count": r.cnt,
            "currency": currency,
        }
        for r in vendor_rows
    ]

    has_data = any(e["total"] > 0 for e in by_year_month)

    return {
        "start_date": start_str,
        "end_date": end_str,
        "primary_currency": currency,
        "has_data": has_data,
        "by_year_month": by_year_month,
        "by_month_of_year": by_month_of_year,
        "by_week_of_month": by_week_of_month,
        "by_week_of_year": by_week_of_year,
        "categories": categories,
        "top_vendors": top_vendors,
    }
