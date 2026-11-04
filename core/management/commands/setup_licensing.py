"""Developer only. Make the signing keys and the demo password's hash for this copy of the code."""

from getpass import getpass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
import json

MIN_LENGTH = 16
PRIVATE_NAME = "licence_private.pem"


def ask_password(label):
    password = getpass(f"{label} (at least {MIN_LENGTH} characters): ")
    if len(password) < MIN_LENGTH:
        raise CommandError(f"The password must have at least {MIN_LENGTH} characters.")
    if getpass("Enter it again: ") != password:
        raise CommandError("The two passwords don't match.")
    return password


def load_private_key(keys_dir):
    path = Path(keys_dir) / PRIVATE_NAME
    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError):
        raise CommandError(f"No private key found at {path}.")


class Command(BaseCommand):
    help = "Developer only. Make the signing keys, and set the demo password."

    def add_arguments(self, parser):
        parser.add_argument("--keys-dir", required=True, help="A folder outside this project. Keep a backup of it.")

    def handle(self, *args, **options):
        keys_dir = Path(options["keys_dir"]).resolve()
        project = Path(settings.BASE_DIR).resolve()
        if keys_dir == project or project in keys_dir.parents:
            raise CommandError("Keep the keys outside this project, so they can't reach the repository.")

        private_path = keys_dir / PRIVATE_NAME
        if private_path.exists():
            key = load_private_key(keys_dir)
            self.stdout.write("Using the existing private key, so registration files already issued keep working.")
        else:
            key = Ed25519PrivateKey.generate()

        password = ask_password("Demo password")
        keys_dir.mkdir(parents=True, exist_ok=True)
        if not private_path.exists():
            private_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
            ))

        out = Path(settings.LICENSING_DIR)
        out.mkdir(parents=True, exist_ok=True)
        (out / "public_key.pem").write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        (out / "demo.json").write_text(json.dumps({"password_hash": make_password(password)}, indent=2) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Done. Back up {private_path}. Never share it."))
        self.stdout.write(f"Safe for the repository: {out / 'public_key.pem'} and {out / 'demo.json'}.")
