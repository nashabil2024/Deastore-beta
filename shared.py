"""Sub-models shared across routers. Keep in sync with frontend/src/lib/types.ts."""

from pydantic import BaseModel


class RobloxProfile(BaseModel):
    username: str
    display_name: str | None = None
    user_id: int | None = None
    avatar_url: str | None = None


class LookupOut(BaseModel):
    status: str  # "found" | "not_found" | "unavailable"
    profile: RobloxProfile | None = None


class FakeFlag(BaseModel):
    kind: str  # "exact" (same bytes) | "similar" (perceptual hash)
    ref_type: str | None = None  # "order" | "topup"
    ref_code: str | None = None


class AiVerdict(BaseModel):
    ai_status: str = "pending"  # "pending" | "done" | "unavailable"
    looks_like_payment_proof: bool | None = None
    detected_amount: int | None = None
    detected_method: str | None = None
    edited_signs: str | None = None
    risk: str | None = None  # "low" | "medium" | "high"
    notes: str | None = None
