"""Update the app on a client's computer from GitHub, with no Git needed.

Only the files that were given to the client in the delivery folder are ever updated, and only when
they've changed. The client's data (instance), documents (media) and Python setup (venv) are never
touched. Everything changed is backed up first, and if anything fails, nothing is left half changed.

It uses Python's standard library only, so it still runs if the app itself can't start.
"""

import json
import shutil
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = "Tajmalookcs/aysha_garments"
BRANCH = "main"
# The version on the clients' computers before this updater existed: the delivery made on 2026-11-06.
START_VERSION = "ef9389ea79ee1d3942438a38b432144cabc18075"

# The same files as the delivery folder. Nothing outside this list is ever downloaded.
APP_FOLDERS = ("billing/", "config/", "core/", "fbr/", "licensing/", "static/", "templates/")
APP_FILES = {
    "manage.py", "requirements.txt", "start.bat", "start_app.vbs", "stop_app.vbs", "backup.bat",
    "update_app.bat", "update_app.py",
}
NEVER = {"tests.py", "testing.py"}

HERE = Path(__file__).resolve().parent
API = "https://api.github.com/repos/" + REPO
RAW = "https://raw.githubusercontent.com/" + REPO
TOO_MANY = 300  # GitHub lists at most 300 changed files in one comparison.


class UpdateError(Exception):
    pass


def is_app_file(path: str) -> bool:
    """True for a file the client was given. Documents, tests and developer files are left out."""
    if not path or path.startswith("/") or ".." in path.split("/"):
        return False
    name = path.rsplit("/", 1)[-1]
    if "__pycache__" in path or name.endswith(".pyc") or name in NEVER:
        return False
    return path in APP_FILES or path.startswith(APP_FOLDERS)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "digital-invoicing-updater"})
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            return reply.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise UpdateError("GitHub is busy or has limited this computer for now. Try again in an hour.")
        if exc.code == 404:
            raise UpdateError("GitHub couldn't find the update. Tell the developer.")
        raise UpdateError(f"GitHub returned an error ({exc.code}). Try again later.")
    except (urllib.error.URLError, socket.timeout, OSError):
        raise UpdateError("Couldn't reach GitHub. Check the internet connection and try again.")


def latest_version(get=_get) -> str:
    return json.loads(get(f"{API}/commits/{BRANCH}"))["sha"]


def changes(base: str, head: str, get=_get) -> list:
    """What to do with each changed app file: ("write", path) or ("delete", path)."""
    data = json.loads(get(f"{API}/compare/{base}...{head}"))
    if data.get("status") not in ("ahead", "identical"):
        raise UpdateError("This copy doesn't match the developer's versions. Tell the developer.")
    files = data.get("files") or []
    if len(files) >= TOO_MANY:
        raise UpdateError("This update is too large to download file by file. Tell the developer.")
    steps = []
    for item in files:
        path, status = item["filename"], item["status"]
        if status == "renamed" and is_app_file(item.get("previous_filename", "")):
            steps.append(("delete", item["previous_filename"]))
        if status == "removed":
            if is_app_file(path):
                steps.append(("delete", path))
        elif is_app_file(path):
            steps.append(("write", path))
    return steps


def apply(steps: list, head: str, root: Path = HERE, get=_get, stamp: str = "") -> Path:
    """Download first, then back up, then change the files. Any failure puts everything back."""
    new = {path: get(f"{RAW}/{head}/{path}") for action, path in steps if action == "write"}

    backup = root / "backups" / f"update_{stamp or datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    if (root / "instance").is_dir():
        shutil.copytree(root / "instance", backup / "instance", dirs_exist_ok=True)
    existed = []
    for _, path in steps:
        target = root / path
        if target.is_file():
            copy = backup / "files" / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, copy)
            existed.append(path)

    try:
        for action, path in steps:
            target = root / path
            if action == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new[path])
            elif target.is_file():
                target.unlink()
    except OSError as exc:
        for action, path in steps:
            if action == "write" and path not in existed:
                (root / path).unlink(missing_ok=True)
        for path in existed:
            shutil.copy2(backup / "files" / path, root / path)
        raise UpdateError(f"A file couldn't be changed ({exc}). Nothing was updated. Close the app and try again.")
    return backup


def app_is_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            return True
    except OSError:
        return False


def log(root: Path, text: str) -> None:
    folder = root / "instance"
    if folder.is_dir():
        with open(folder / "update.log", "a", encoding="utf-8") as out:
            out.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")


def main(root: Path = HERE) -> int:
    if app_is_running():
        print("The app is open. Close it with Stop Digital Invoicing on the desktop, then run this again.")
        return 1
    version_file = root / "instance" / "app_version.txt"
    try:
        current = version_file.read_text(encoding="utf-8").strip() or START_VERSION
    except OSError:
        current = START_VERSION
    try:
        head = latest_version()
        if head == current:
            print("This copy is already up to date.")
            return 0
        steps = changes(current, head)
        backup = apply(steps, head, root)
    except UpdateError as exc:
        print(exc)
        log(root, f"Failed: {exc}")
        return 1
    version_file.parent.mkdir(exist_ok=True)
    version_file.write_text(head + "\n", encoding="utf-8")
    written = sum(1 for action, _ in steps if action == "write")
    removed = len(steps) - written
    print(f"Updated: {written} file(s) changed, {removed} removed. A backup is in {backup}.")
    log(root, f"Updated {current[:7]} to {head[:7]}: {written} changed, {removed} removed. Backup {backup.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
