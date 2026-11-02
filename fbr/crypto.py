"""Encrypts PRAL tokens at rest. The key is created locally and is never committed."""

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    path = settings.INSTANCE_DIR / "fbr_key.txt"
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes().strip())


def encrypt(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt(stored: str) -> str:
    return _fernet().decrypt(stored.encode()).decode()
