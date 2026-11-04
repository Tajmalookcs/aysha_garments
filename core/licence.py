"""Demo period and registration.

A new install runs as a 15 day demo. A registration file ends the demo. It is signed with the
developer's private key, which never leaves the developer's computer, so the app only holds the
public key. This stops a made-up file, but it can't stop someone who changes the code itself.
"""

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone

DEMO_DAYS = 15
MAX_FILE_BYTES = 64 * 1024


class LicenceError(ValueError):
    """A problem with a registration file. The message is shown on screen."""


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def demo_password_hash() -> str:
    """Empty if this copy hasn't been prepared by the developer yet."""
    try:
        return json.loads((Path(settings.LICENSING_DIR) / "demo.json").read_text())["password_hash"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def _public_key():
    try:
        return load_pem_public_key((Path(settings.LICENSING_DIR) / "public_key.pem").read_bytes())
    except (OSError, ValueError):
        return None


def read_file(raw: bytes) -> dict:
    """The registration details, if the file is one the developer signed."""
    if len(raw) > MAX_FILE_BYTES:
        raise LicenceError("This isn't a registration file. It's too large.")
    try:
        data = json.loads(raw)
        payload = data["payload"]
        signature = base64.b64decode(data["signature"], validate=True)
        ntn = payload["ntn"]
        name = payload["business_name"]
        password_hash = payload["password_hash"]
    except (ValueError, KeyError, TypeError):
        raise LicenceError("This isn't a registration file. Ask the developer for the right one.")
    if not all(isinstance(value, str) and value for value in (ntn, name, password_hash)):
        raise LicenceError("This isn't a registration file. Ask the developer for the right one.")
    key = _public_key()
    if key is None:
        raise LicenceError("This copy can't check registration files yet. Ask the developer.")
    try:
        key.verify(signature, canonical(payload))
    except (InvalidSignature, TypeError, ValueError):
        raise LicenceError("This registration file isn't valid. Ask the developer for a new one.")
    return payload


def installed(company):
    """The registration details, only if a valid file for this company's NTN is in place."""
    try:
        payload = read_file(Path(settings.LICENCE_FILE).read_bytes())
    except (OSError, LicenceError):
        return None
    return payload if company is not None and payload["ntn"] == company.ntn else None


def install(company, raw: bytes) -> dict:
    """Check a registration file and put it in place. This ends the demo."""
    payload = read_file(raw)
    if payload["ntn"] != company.ntn:
        raise LicenceError(f"This file is for NTN {payload['ntn']}, not this company's NTN. Ask the developer for the right one.")
    target = Path(settings.LICENCE_FILE)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, target)
    return payload


def check_developer_password(password: str, company=None) -> bool:
    payload = installed(company)
    stored = payload["password_hash"] if payload else demo_password_hash()
    return bool(stored) and check_password(password, stored)


@dataclass
class Status:
    registered: bool
    business_name: str = ""
    ntn: str = ""
    days_left: int = 0
    clock_moved_back: bool = False

    @property
    def expired(self):
        return not self.registered and (self.days_left <= 0 or self.clock_moved_back)

    @property
    def active(self):
        return not self.expired


def status(company) -> Status:
    payload = installed(company)
    if payload:
        return Status(True, payload["business_name"], payload["ntn"])

    today = timezone.localdate()
    changed = []
    if company.demo_started_on is None:
        company.demo_started_on = today
        changed.append("demo_started_on")
    clock_moved_back = company.demo_last_seen is not None and today < company.demo_last_seen
    if company.demo_last_seen is None or today > company.demo_last_seen:
        company.demo_last_seen = today
        changed.append("demo_last_seen")
    if changed:
        company.save(update_fields=changed)
    used = (today - company.demo_started_on).days
    return Status(False, days_left=max(DEMO_DAYS - used, 0), clock_moved_back=clock_moved_back)
