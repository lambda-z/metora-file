from __future__ import annotations

import tempfile

from app.modules.auth import security
from app.storage.local import LocalBackend
from app.storage.signing import sign, verify_signature


def test_api_token_hash_roundtrip():
    raw = security.generate_api_token(env="test")
    assert raw.startswith("metora_test_")
    assert security.token_prefix(raw) == raw[:14]
    # Same raw value hashes deterministically; different values differ.
    assert security.hash_token(raw) == security.hash_token(raw)
    assert security.hash_token(raw) != security.hash_token(raw + "x")


def test_share_password_roundtrip():
    hashed = security.hash_password("s3cret")
    assert security.verify_password("s3cret", hashed)
    assert not security.verify_password("wrong", hashed)
    assert not security.verify_password("anything", "")


def test_local_storage_put_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalBackend(root=tmp, base_url="http://test")
        key = backend.build_key(bucket="b1", object_key=None, filename="hello.txt")
        meta = backend.put_object(key=key, data=b"hello world", content_type="text/plain")
        assert meta["size"] == 11
        with backend.open_stream(key=key) as fh:
            assert fh.read() == b"hello world"
        url = backend.get_download_url(key=key, expires=60, filename="hello.txt")
        assert url.startswith("http://test/files/")
        backend.delete(key=key)


def test_download_signature_verification():
    sig = sign("b1/abc/hello.txt", 9999999999)
    assert verify_signature("b1/abc/hello.txt", 9999999999, sig)
    assert not verify_signature("b1/abc/hello.txt", 9999999999, "deadbeef")
    # Already-expired timestamp must fail.
    assert not verify_signature("b1/abc/hello.txt", 1, sign("b1/abc/hello.txt", 1))
