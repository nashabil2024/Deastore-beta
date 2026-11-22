"""Optional WhatsApp Cloud API alerts for store-admin transactions.

The token stays in the server environment and is never included in API responses.
Messages use a pre-approved WhatsApp template so the store can notify its own admin.
"""

import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)


def whatsapp_alert_status() -> dict:
    keys = (
        "WHATSAPP_CLOUD_API_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_NOTIFY_TO",
        "WHATSAPP_TEMPLATE_NAME",
    )
    missing = [key for key in keys if not os.getenv(key, "").strip()]
    return {"configured": not missing, "missing": missing}


async def send_admin_transaction_alert(code: str, kind: str, detail: str, amount: str) -> None:
    if not whatsapp_alert_status()["configured"]:
        return

    token = os.environ["WHATSAPP_CLOUD_API_TOKEN"].strip()
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"].strip()
    recipient = re.sub(r"\D", "", os.environ["WHATSAPP_NOTIFY_TO"])
    template_name = os.environ["WHATSAPP_TEMPLATE_NAME"].strip()
    language = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "id").strip() or "id"
    version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v27.0").strip() or "v27.0"
    if not recipient:
        logger.warning("WhatsApp alert skipped: WHATSAPP_NOTIFY_TO has no digits")
        return

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": code[:40]},
                    {"type": "text", "text": kind[:80]},
                    {"type": "text", "text": detail[:120]},
                    {"type": "text", "text": amount[:80]},
                ],
            }],
        },
    }
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
        if response.is_error:
            logger.warning("WhatsApp alert failed (HTTP %s)", response.status_code)
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp alert request failed (%s)", type(exc).__name__)
