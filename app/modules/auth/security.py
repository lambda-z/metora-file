from __future__ import annotations

import hashlib
import secrets

import bcrypt

TOKEN_PREFIX_LEN = 14


def generate_api_token(env: str = "live") -> str:
    """Generate a raw API token: ``metora_<env>_<urlsafe-random>``.

    The raw value is shown to the user exactly once; only the hash is stored.
    """
    random_part = secrets.token_urlsafe(32)
    return f"metora_{env}_{random_part}"


def hash_token(raw_token: str) -> str:
    """Deterministic hash for API-token lookup (sha256, hex)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def token_prefix(raw_token: str) -> str:
    return raw_token[:TOKEN_PREFIX_LEN]


# ---- Share-link passwords (salted, slow hash) ----

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---- Share tokens (opaque, looked up by hash) ----

def generate_share_token() -> str:
    return secrets.token_urlsafe(24)


def hash_share_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
