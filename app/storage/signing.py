from __future__ import annotations

import hashlib
import hmac
import time

from app.config import settings


def _message(key: str, expires_at: int) -> bytes:
    return f"{key}:{expires_at}".encode("utf-8")


def sign(key: str, expires_at: int) -> str:
    return hmac.new(
        settings.signing_secret.encode("utf-8"),
        _message(key, expires_at),
        hashlib.sha256,
    ).hexdigest()


def make_signed_query(key: str, expires_in: int) -> tuple[int, str]:
    """Return (expires_at_epoch, signature) for a local download URL."""
    expires_at = int(time.time()) + max(1, expires_in)
    return expires_at, sign(key, expires_at)


def verify_signature(key: str, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign(key, expires_at)
    return hmac.compare_digest(expected, signature)
