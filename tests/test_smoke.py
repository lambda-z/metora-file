from __future__ import annotations

import tempfile

import pytest

from app.modules.auth import security
from app.storage.base import normalize_folder
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


def test_upload_signature_is_separate_from_download():
    key = "b1/abc/hello.txt"
    put_sig = sign(key, 9999999999, action="put")
    get_sig = sign(key, 9999999999, action="get")
    # PUT and GET signatures must differ so a download token can't be replayed
    # as an upload token and vice-versa.
    assert put_sig != get_sig
    assert verify_signature(key, 9999999999, put_sig, action="put")
    assert not verify_signature(key, 9999999999, put_sig, action="get")
    assert not verify_signature(key, 9999999999, get_sig, action="put")


def test_local_presigned_put_url_and_stat():
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalBackend(root=tmp, base_url="http://test")
        key = backend.build_key(bucket="b1", object_key=None, filename="hi.txt")
        upload = backend.presigned_put_url(key=key, expires=60, content_type="text/plain")
        assert upload["method"] == "PUT"
        assert upload["url"].startswith("http://test/files/")
        assert upload["headers"]["Content-Type"] == "text/plain"
        # stat before upload must raise (no body yet).
        with pytest.raises(FileNotFoundError):
            backend.stat_object(key=key)
        backend.put_object(key=key, data=b"hello world", content_type="text/plain")
        stat = backend.stat_object(key=key)
        assert stat["size"] == 11
        assert stat["etag"]


def test_normalize_folder():
    assert normalize_folder(None) == ""
    assert normalize_folder("") == ""
    assert normalize_folder("/") == ""
    assert normalize_folder("images") == "images"
    assert normalize_folder("/images/2024/") == "images/2024"
    # Collapses empties and strips traversal segments.
    assert normalize_folder("a//b/./c") == "a/b/c"
    assert normalize_folder("../../etc/passwd") == "etc/passwd"
    # Unsafe characters in a segment are sanitised to hyphens.
    assert normalize_folder("a b/c?d") == "a-b/c-d"


def test_build_key_with_folder_prefixes_path():
    backend = LocalBackend(root="/tmp/does-not-matter", base_url="http://test")
    # Folder is prefixed under the bucket; the random uuid + filename follow.
    key = backend.build_key(
        bucket="b1", object_key=None, filename="hi.txt", folder="images/2024"
    )
    assert key.startswith("b1/images/2024/")
    assert key.endswith("/hi.txt")

    # Folder + explicit object_key keeps the folder as a prefix.
    key2 = backend.build_key(
        bucket="b1", object_key="sub/file.pdf", filename="hi.txt", folder="docs"
    )
    assert key2 == "b1/docs/sub/file.pdf"

    # No folder behaves exactly as before (no extra prefix).
    key3 = backend.build_key(bucket="b1", object_key="file.txt", filename="x")
    assert key3 == "b1/file.txt"


def test_folder_aware_download_url_reflects_folder():
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalBackend(root=tmp, base_url="http://test")
        key = backend.build_key(
            bucket="b1", object_key=None, filename="hi.txt", folder="images"
        )
        backend.put_object(key=key, data=b"hi", content_type="text/plain")
        url = backend.get_download_url(key=key, expires=60, filename="hi.txt")
        # The signed download URL carries the folder segment in its path.
        assert "/files/b1/images/" in url
