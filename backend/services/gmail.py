"""
services/gmail.py – Gmail API client.

Provides:
  build_gmail_service(credentials)  – build the Gmail API service object
  search_order_emails(service)      – search for order-related emails
  get_email_details(service, id)    – fetch and parse a single email
"""

import base64
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import html2text
from googleapiclient.discovery import build as google_build

# Gmail search query – broad enough to catch all major vendors
_ORDER_QUERY = (
    "subject:(order OR shipment OR shipping OR tracking OR "
    "delivered OR receipt OR invoice OR purchase OR confirmation OR dispatch) "
    "-category:social -category:promotions -category:forums"
)

_HTML_TO_TEXT = html2text.HTML2Text()
_HTML_TO_TEXT.ignore_links = False
_HTML_TO_TEXT.ignore_images = True
_HTML_TO_TEXT.body_width = 0  # Don't wrap


def build_gmail_service(credentials):
    """Build and return an authenticated Gmail API service."""
    return google_build("gmail", "v1", credentials=credentials)


def search_order_emails(service, max_results: int = 200) -> list[str]:
    """
    Search the user's Gmail inbox for order-related emails.
    Returns a list of Gmail message IDs (strings).
    """
    message_ids = []
    page_token = None

    while len(message_ids) < max_results:
        params = {
            "userId": "me",
            "q": _ORDER_QUERY,
            "maxResults": min(100, max_results - len(message_ids)),
        }
        if page_token:
            params["pageToken"] = page_token

        result = service.users().messages().list(**params).execute()
        messages = result.get("messages", [])
        message_ids.extend(m["id"] for m in messages)

        page_token = result.get("nextPageToken")
        if not page_token or len(message_ids) >= max_results:
            break

    return message_ids[:max_results]


def get_email_details(service, message_id: str) -> dict:
    """
    Fetch a single Gmail message and return a structured dict:
    {
        "id": str,
        "subject": str,
        "from": str,
        "date": datetime | None,
        "body_text": str,   # plain text (preferred)
        "snippet": str,
    }
    Adds a small delay to stay within Gmail API quota.
    """
    time.sleep(0.1)  # 100ms between calls → max 10/sec (50 quota units/sec, well under 250 limit)

    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    payload = msg.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    subject = headers.get("subject", "(no subject)")
    from_addr = headers.get("from", "")
    date_str = headers.get("date", "")

    date: Optional[datetime] = None
    if date_str:
        try:
            date = parsedate_to_datetime(date_str)
        except Exception:
            date = None

    # Recursively extract body text
    plain_parts: list[str] = []
    html_parts: list[str] = []
    _extract_parts(payload, plain_parts, html_parts)

    if plain_parts:
        body_text = "\n".join(plain_parts)
    elif html_parts:
        # Convert HTML to readable plain text
        body_text = _HTML_TO_TEXT.handle("\n".join(html_parts))
    else:
        body_text = msg.get("snippet", "")

    return {
        "id": message_id,
        "subject": subject,
        "from": from_addr,
        "date": date,
        "body_text": body_text,
        "snippet": msg.get("snippet", ""),
    }


# ─── Private helpers ──────────────────────────────────────────────────────────

def _decode_body(data: str) -> str:
    """Decode base64url-encoded Gmail body data."""
    # Gmail strips the '=' padding – we need to add it back
    padded = data + "=="
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_parts(part: dict, plain_parts: list, html_parts: list) -> None:
    """
    Recursively walk the MIME part tree collecting text/plain and text/html content.
    Handles multipart/mixed, multipart/alternative, multipart/related nesting.
    """
    mime_type = part.get("mimeType", "")

    if mime_type.startswith("multipart/"):
        for sub_part in part.get("parts", []):
            _extract_parts(sub_part, plain_parts, html_parts)
        return

    body = part.get("body", {})
    data = body.get("data", "")

    if not data:
        return

    decoded = _decode_body(data)

    if mime_type == "text/plain":
        plain_parts.append(decoded)
    elif mime_type == "text/html":
        html_parts.append(decoded)
