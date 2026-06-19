from __future__ import annotations

import hashlib
import hmac
import time

from app.config import settings


def _message(key: str, expires_at: int, action: str = "get") -> bytes:
    return f"{action}:{key}:{expires_at}".encode("utf-8")


def sign(key: str, expires_at: int, action: str = "get") -> str:
    return hmac.new(
        settings.signing_secret.encode("utf-8"),
        _message(key, expires_at, action),
        hashlib.sha256,
    ).hexdigest()


def make_signed_query(key: str, expires_in: int, action: str = "get") -> tuple[int, str]:
    """Return (expires_at_epoch, signature) for a signed local URL.

    ``action`` distinguishes download (``get``) from upload (``put``) signatures
    so a download token can never be replayed as an upload token.
    """
    expires_at = int(time.time()) + max(1, expires_in)
    return expires_at, sign(key, expires_at, action)


def verify_signature(
    key: str, expires_at: int, signature: str, action: str = "get"
) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign(key, expires_at, action)
    return hmac.compare_digest(expected, signature)
