import json
from datetime import datetime, timezone
import requests
import streamlit as st


def _post_discord_webhook(
    secret_name: str,
    payload: dict,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> bool:
    """Safely send an embed (and optional image) to a Discord webhook from st.secrets."""
    webhook_url = st.secrets.get(secret_name, "")
    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return False

    payload["allowed_mentions"] = {"parse": []}

    try:
        if file_bytes and filename:
            files = {
                "file": (filename, file_bytes, "image/png" if filename.endswith(".png") else "image/jpeg")
            }
            resp = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=12,
            )
        else:
            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
            )
        return 200 <= resp.status_code < 300
    except requests.RequestException:
        return False


def send_order_webhook(
    order_id: str,
    name: str,
    address: str,
    phone: str,
    payment_method: str,
    items: list[dict],
    grand_total: int,
    receipt_bytes: bytes | None = None,
    receipt_filename: str | None = None,
) -> bool:
    items_summary = "\n".join(
        f"• **{item['name']}** x {item['qty']} — `PKR {item['price'] * item['qty']:,}/-`"
        for item in items
    )

    embed = {
        "title": f"New Order Received — {order_id}",
        "color": 0xD4AF37,
        "fields": [
            {"name": "Order ID", "value": f"`{order_id}`", "inline": True},
            {"name": "Payment Method", "value": payment_method, "inline": True},
            {"name": "Grand Total", "value": f"**PKR {grand_total:,}/-**", "inline": True},
            {"name": "Customer Name", "value": name, "inline": True},
            {"name": "Phone", "value": phone, "inline": True},
            {"name": "Delivery Address", "value": address, "inline": False},
            {"name": "Order Items", "value": items_summary, "inline": False},
        ],
        "footer": {"text": "Waqar Foodies • Order Pipeline"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if receipt_bytes and receipt_filename:
        embed["image"] = {"url": f"attachment://{receipt_filename}"}

    return _post_discord_webhook(
        "DISCORD_ORDER_WEBHOOK",
        {"username": "Waqar Foodies Orders", "embeds": [embed]},
        file_bytes=receipt_bytes,
        filename=receipt_filename,
    )


def send_review_webhook(stars: int, review_text: str, reviewer_name: str = "Guest") -> bool:
    embed = {
        "title": "New Customer Review",
        "color": 0xE5B84B,
        "fields": [
            {"name": "Reviewer", "value": reviewer_name or "Guest", "inline": True},
            {"name": "Rating", "value": f"{stars} / 5 Stars", "inline": True},
            {"name": "Review", "value": review_text, "inline": False},
        ],
        "footer": {"text": "Waqar Foodies • Reviews"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return _post_discord_webhook(
        "DISCORD_REVIEW_WEBHOOK",
        {"username": "Waqar Foodies Reviews", "embeds": [embed]},
    )


def send_bug_webhook(bug_text: str, reporter_name: str = "Anonymous") -> bool:
    embed = {
        "title": "New Bug Report",
        "color": 0xC94A4A,
        "fields": [
            {"name": "Reporter", "value": reporter_name or "Anonymous", "inline": True},
            {"name": "Bug Description", "value": bug_text, "inline": False},
        ],
        "footer": {"text": "Waqar Foodies • Bug Tracker"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return _post_discord_webhook(
        "DISCORD_BUG_WEBHOOK",
        {"username": "Waqar Foodies Bugs", "embeds": [embed]},
    )
