"""
services/classifier.py – Email classification using Claude.

Classifies each email into one of four categories:
  - order_confirmation
  - shipping_update
  - delivery_confirmation
  - irrelevant
"""

import json
import os
import time

import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

_SYSTEM_PROMPT = """You are an email classifier for a package tracking system.

Classify the given email into EXACTLY ONE of these categories:
- order_confirmation: An email confirming a new purchase/order was placed (contains order ID, items, price)
- shipping_update: An email with shipping or tracking updates for an existing order (tracking number, carrier, shipment dispatched)
- delivery_confirmation: An email confirming a package has been delivered
- irrelevant: Not related to orders or package deliveries (newsletters, promotions, account updates, etc.)

Respond with ONLY a valid JSON object — no markdown, no explanation:
{"category": "<category>", "confidence": <float 0.0-1.0>, "reason": "<one sentence>"}"""


def classify_email(subject: str, from_addr: str, body: str) -> dict:
    """
    Classify an email using Claude.

    Args:
        subject:   Email subject line
        from_addr: Sender address (e.g. "Amazon <no-reply@amazon.com>")
        body:      Email body text (will be truncated to 2000 chars)

    Returns:
        dict with keys: category, confidence, reason
        Falls back to {"category": "irrelevant", "confidence": 0.0, "reason": "parse error"}
        if Claude returns malformed JSON.
    """
    # 2000 chars is enough for classification – key data is near the top of order emails
    truncated_body = body[:2000]
    user_message = f"Subject: {subject}\nFrom: {from_addr}\n\n{truncated_body}"

    result = _call_with_retry(user_message, max_tokens=150)

    try:
        parsed = json.loads(result)
        # Validate expected keys are present
        if "category" not in parsed:
            raise ValueError("Missing 'category' key")
        return parsed
    except (json.JSONDecodeError, ValueError):
        return {"category": "irrelevant", "confidence": 0.0, "reason": "parse error"}


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
            if e.status_code == 529 and attempt < retries:  # Overloaded
                time.sleep(delay)
                delay *= 2
            else:
                raise
    return ""
