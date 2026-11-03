"""Back up the database, the keys and the client documents to a folder outside the project."""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

RESTORE = """To restore this backup:
1. Close the app.
2. Copy db.sqlite3, secret_key.txt and fbr_key.txt into the project's instance folder, replacing what's there.
3. Copy the media folder into the project, if it's in this backup.
4. Run start.bat.

Keep this folder private. It holds client records and the key that unlocks the saved FBR token.
"""


class Command(BaseCommand):
    help = "Back up the database, keys and media. Safe to run while the app is open."

    def add_arguments(self, parser):
        parser.add_argument("target", help="Folder to create the backup in, outside the project.")

    def handle(self, *args, **options):
        target = Path(options["target"]).expanduser().resolve()
        project = Path(settings.BASE_DIR).resolve()
        if target == project or project in target.parents:
            raise CommandError("Choose a folder outside the project, so a backup can't end up on GitHub.")
        database = Path(settings.DATABASES["default"]["NAME"])
        if not database.exists():
            raise CommandError("There's nothing to back up yet. Run start.bat and set up a company first.")

        folder = target / f"backup_{datetime.now():%Y-%m-%d_%H%M%S}"
        try:
            folder.mkdir(parents=True)
            self._copy_database(database, folder / "db.sqlite3")
            copied = ["database"]
            for name in ("secret_key.txt", "fbr_key.txt"):
                source = database.parent / name
                if source.exists():
                    shutil.copy2(source, folder / name)
                    copied.append(name)
            media = project / "media"
            files = [p for p in media.rglob("*") if p.is_file() and p.name != ".gitkeep"] if media.exists() else []
            if files:
                shutil.copytree(media, folder / "media", ignore=shutil.ignore_patterns(".gitkeep"))
                copied.append(f"{len(files)} media files")
            (folder / "HOW_TO_RESTORE.txt").write_text(RESTORE, encoding="utf-8")
        except (OSError, sqlite3.Error) as exc:
            raise CommandError(f"The backup failed: {exc}. Check the folder and try again.")
        self.stdout.write(f"Backup saved in {folder}")
        self.stdout.write("Includes: " + ", ".join(copied))

    @staticmethod
    def _copy_database(source, destination):
        """SQLite's own backup gives a complete copy even while the app is writing."""
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = sqlite3.connect(destination)
        try:
            with dst:
                src.backup(dst)
            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            src.close()
            dst.close()
        if result != "ok":
            raise sqlite3.Error("the backup copy failed its check")
