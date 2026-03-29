"""
services/extractor.py – Structured data extraction from order emails using Claude.

Extracts order/shipment fields and returns them as a validated dict.
"""

import json
import os
import re
import time
from typing import Optional

import anthropic
from dateutil import parser as dateutil_parser

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

_SYSTEM_PROMPT = """You are a data extraction assistant for a package tracking system.

Extract order and shipment information from the provided email.
Return a JSON object matching this EXACT schema (use null for any missing fields):
{
  "vendor": "store or company name as a string",
  "vendor_order_id": "the order ID/number assigned by the vendor, or null",
  "order_date": "ISO 8601 date string (YYYY-MM-DD) or null",
  "total_price": number (numeric value only, no currency symbol) or null,
  "currency": "3-letter ISO currency code (e.g. USD, EUR, GBP) or null",
  "status": "one of: ordered, shipped, delivered, unknown",
  "items": [
    {
      "name": "product name as string",
      "quantity": integer (default 1 if unclear),
      "unit_price": number or null,
      "category": "product category string or null"
    }
  ],
  "tracking_number": "shipping tracking number string or null",
  "carrier": "carrier name (UPS / FedEx / USPS / DHL / OnTrac / etc.) or null",
  "estimated_delivery": "ISO 8601 date string (YYYY-MM-DD) or null",
  "tracking_url": "full URL string or null"
}

Rules:
- Normalize ALL dates to ISO 8601 format (YYYY-MM-DD)
- items array must have at least one entry for order_confirmation emails; can be empty [] for shipping/delivery emails
- Return ONLY the JSON object — no markdown fences, no explanation text"""


def extract_order_data(subject: str, from_addr: str, body: str, category: str, email_date=None) -> dict:
    """
    Extract structured order data from an email using Claude.

    Args:
        subject:   Email subject line
        from_addr: Sender address
        body:      Email body text (truncated to 8000 chars)
        category:  The email category from classifier (provides context to Claude)

    Returns:
        Extracted data dict matching the schema above.
        Returns a minimal dict with nulls on parse error.
    """
    # Use up to 8000 chars for extraction – more context is needed vs classification
    truncated_body = body[:8000]
    date_hint = f"Email received: {email_date.strftime('%Y-%m-%d')}\n" if email_date else ""
    user_message = (
        f"Email category: {category}\n"
        f"Subject: {subject}\n"
        f"From: {from_addr}\n"
        f"{date_hint}"
        f"\n{truncated_body}"
    )

    raw = _call_with_retry(user_message, max_tokens=1024)
    raw = _strip_markdown_fences(raw)

    try:
        data = json.loads(raw)
        data = _normalize_dates(data)
        return data
    except (json.JSONDecodeError, ValueError):
        # Return a minimal empty extraction rather than crashing
        return _empty_extraction()


def _strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences that Claude sometimes adds despite instructions.
    Handles ```json ... ``` and ``` ... ```
    """
    text = text.strip()
    # Match ```json or ``` at start
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _normalize_dates(data: dict) -> dict:
    """
    Secondary date normalization pass using dateutil.
    If Claude returned a non-ISO date string, try to parse and reformat it.
    """
    date_fields = ["order_date", "estimated_delivery"]
    for field in date_fields:
        val = data.get(field)
        if val and isinstance(val, str):
            # Already ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            if re.match(r"^\d{4}-\d{2}-\d{2}", val):
                # Keep just the date part
                data[field] = val[:10]
                continue
            # Try to parse other formats
            try:
                parsed = dateutil_parser.parse(val, default=None)
                data[field] = parsed.strftime("%Y-%m-%d")
            except Exception:
                data[field] = None  # Can't parse → null is better than garbage

    return data


def _empty_extraction() -> dict:
    """Return a minimal empty extraction dict when parsing fails."""
    return {
        "vendor": None,
        "vendor_order_id": None,
        "order_date": None,
        "total_price": None,
        "currency": None,
        "status": "unknown",
        "items": [],
        "tracking_number": None,
        "carrier": None,
        "estimated_delivery": None,
        "tracking_url": None,
    }


def _call_with_retry(user_message: str, max_tokens: int, retries: int = 3) -> str:
    """Call Claude with exponential backoff on rate-limit errors."""
    delay = 1
    for attempt in range(retries + 1):
        try:
            response = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except anthropic.RateLimitError:
            if attempt == retries:
                raise
            print(f"Rate limited. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < retries:
                time.sleep(delay)
                delay *= 2
            else:
                raise
    return ""
