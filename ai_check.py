"""AI verification of payment proofs via Gemini vision (Emergent LLM universal key).

Degrades gracefully: when the key is missing or the call fails, analyze_proof returns
None and the doc is marked ai_status="unavailable" so the admin reviews manually.
"""

import base64
import json
import logging
import os
import uuid

from lib.db import db

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Kamu adalah analis keamanan pembayaran untuk toko top-up game Indonesia. "
    "Analisis gambar bukti pembayaran (screenshot QRIS, e-wallet, atau transfer bank). "
    "Balas HANYA dengan JSON valid tanpa teks lain, dengan format persis: "
    '{"looks_like_payment_proof": true atau false, "detected_amount": angka atau null, '
    '"detected_method": "qris" / "dana" / "gopay" / "ovo" / "shopeepay" / "bca" / "mandiri" / "bri" / "lainnya" / null, '
    '"edited_signs": "tanda-tanda editan, foto ulang, atau penggunaan ulang (atau null jika tidak ada)", '
    '"risk": "low" / "medium" / "high", '
    '"notes": "penjelasan singkat dalam bahasa Indonesia"}'
)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


async def analyze_proof(content: bytes, mime: str, expected_amount: int | None) -> dict | None:
    """Verdict dict, atau None saat AI tidak tersedia (fallback: review manual admin)."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY tidak diset — analisis AI bukti dilewati")
        return None
    try:
        from emergentintegrations.llm.chat import (
            ImageContent,
            LlmChat,
            StreamDone,
            TextDelta,
            UserMessage,
        )

        chat = (
            LlmChat(
                api_key=api_key,
                session_id=f"proof-check-{uuid.uuid4()}",
                system_message=SYSTEM_PROMPT,
            )
            .with_model("gemini", "gemini-2.5-flash")
        )
        prompt = "Analisis bukti pembayaran ini"
        if expected_amount:
            prompt += f". Nominal yang seharusnya dibayar: Rp{expected_amount:,}".replace(",", ".")
        message = UserMessage(
            text=prompt,
            file_contents=[ImageContent(image_base64=base64.b64encode(content).decode())],
        )
        out = ""
        async for ev in chat.stream_message(message):
            if isinstance(ev, TextDelta):
                out += ev.content
            elif isinstance(ev, StreamDone):
                break

        parsed = _extract_json(out)
        if not parsed:
            logger.warning("AI verdict tidak bisa di-parse: %.200s", out)
            return None
        risk = parsed.get("risk")
        return {
            "looks_like_payment_proof": bool(parsed.get("looks_like_payment_proof")),
            "detected_amount": (
                int(parsed["detected_amount"])
                if isinstance(parsed.get("detected_amount"), (int, float))
                else None
            ),
            "detected_method": parsed.get("detected_method") or None,
            "edited_signs": parsed.get("edited_signs") or None,
            "risk": risk if risk in ("low", "medium", "high") else "medium",
            "notes": parsed.get("notes") or "",
        }
    except Exception as exc:
        logger.warning("Analisis AI bukti gagal: %s", exc)
        return None


async def run_ai_check(kind: str, doc_id: str, content: bytes, mime: str, expected_amount: int | None) -> None:
    """Background task: simpan verdict ke dokumen order / coin_topups."""
    verdict = await analyze_proof(content, mime, expected_amount)
    coll = db.orders if kind == "order" else db.coin_topups
    if verdict is None:
        await coll.update_one({"id": doc_id}, {"$set": {"ai_verdict.ai_status": "unavailable"}})
    else:
        verdict["ai_status"] = "done"
        await coll.update_one({"id": doc_id}, {"$set": {"ai_verdict": verdict}})
