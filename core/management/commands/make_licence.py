"""Developer only. Make a client's registration file."""

import base64
import json
import re
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.licence import canonical

from .setup_licensing import ask_password, load_private_key


class Command(BaseCommand):
    help = "Developer only. Make a registration file for one client's NTN."

    def add_arguments(self, parser):
        parser.add_argument("--keys-dir", required=True)
        parser.add_argument("--ntn", required=True, help="The client's NTN, as 0000000-0.")
        parser.add_argument("--name", required=True, help="The client's business name.")
        parser.add_argument("--out", required=True, help="Where to save the file. Keep it out of this project's tracked files.")

    def handle(self, *args, **options):
        if not re.fullmatch(r"\d{7}-\d", options["ntn"]):
            raise CommandError("The NTN must look like 0000000-0.")
        key = load_private_key(options["keys_dir"])
        password = ask_password("Developer password for this client")
        payload = {
            "business_name": options["name"],
            "issued_on": timezone.localdate().isoformat(),
            "ntn": options["ntn"],
            "password_hash": make_password(password),
        }
        signature = base64.b64encode(key.sign(canonical(payload))).decode()
        Path(options["out"]).write_text(json.dumps({"payload": payload, "signature": signature}, indent=2) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Saved {options['out']}. Give this file to {options['name']} only."))
