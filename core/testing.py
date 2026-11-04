"""Test helpers: a throwaway signing key and licence folder, so tests never touch real ones."""

import base64
import json
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.contrib.auth.hashers import make_password
from django.test import override_settings

from .licence import canonical

DEMO_PASSWORD = "demo-password-for-tests"
DEVELOPER_PASSWORD = "developer-password-for-tests"
_HASHES = {}


def _hash(password):
    if password not in _HASHES:
        _HASHES[password] = make_password(password)
    return _HASHES[password]


def use_test_licensing(test, *, prepared=True):
    """Point the app at a temporary licence folder for this test. Returns the signing key."""
    folder = Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, folder, ignore_errors=True)
    override = override_settings(LICENSING_DIR=folder, LICENCE_FILE=folder / "licence.json")
    override.enable()
    test.addCleanup(override.disable)
    key = Ed25519PrivateKey.generate()
    if prepared:
        (folder / "public_key.pem").write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        (folder / "demo.json").write_text(json.dumps({"password_hash": _hash(DEMO_PASSWORD)}))
    test.signing_key = key
    test.licence_folder = folder
    return key


def licence_bytes(key, ntn, name="Test Company", password=DEVELOPER_PASSWORD) -> bytes:
    payload = {"business_name": name, "issued_on": "2026-11-04", "ntn": ntn, "password_hash": _hash(password)}
    signature = base64.b64encode(key.sign(canonical(payload))).decode()
    return json.dumps({"payload": payload, "signature": signature}).encode()


def register_copy(test, company):
    """Set up a temporary licence folder with a registered copy for this company."""
    key = use_test_licensing(test)
    (test.licence_folder / "licence.json").write_bytes(licence_bytes(key, company.ntn))
