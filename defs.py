"""Shared constants and small helpers."""

import random
import string

PAYMENT_MANUAL = (
    "qris", "dana", "gopay", "ovo", "shopeepay",
    "bca", "bri", "bni", "mandiri", "btn", "bsi", "cimb", "danamon", "permata",
    "maybank", "ocbc", "panin", "mega", "sinarmas", "jenius", "jago", "blu", "seabank",
    "allo", "neo", "bank_dki", "bjb", "jateng", "jatim", "bali", "diy", "sumut",
    "sumselbabel", "kalbar", "kalsel", "kaltimtara", "sulselbar", "nagari", "ntb", "ntt",
    "maluku", "malut", "bengkulu", "papua",
)
PAYMENT_METHODS = PAYMENT_MANUAL + ("coin",)

ORDER_STATUSES = ("menunggu_pembayaran", "menunggu_verifikasi", "diproses", "selesai", "ditolak")
TOPUP_STATUSES = ("menunggu_pembayaran", "menunggu_verifikasi", "disetujui", "ditolak")


def new_code(prefix: str) -> str:
    """Human-friendly order/topup code, e.g. DEA-8F3K2."""
    alphabet = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(random.choices(alphabet, k=5))}"
