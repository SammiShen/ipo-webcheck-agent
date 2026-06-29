from pathlib import Path
from datetime import datetime
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parent

BACKUP_DIR = PROJECT_ROOT / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
zip_path = BACKUP_DIR / f"ipo_webcheck_agent_backup_{time_str}.zip"


EXCLUDE_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    ".gradio",
    "output",
    "court_profile",
    "zx_profile",
    "chrome_debug_profile",
    "backups",
}

EXCLUDE_FILES = {
    "court_login.json",
}


def should_exclude(path: Path):
    relative_parts = path.relative_to(PROJECT_ROOT).parts

    for part in relative_parts:
        if part in EXCLUDE_DIRS:
            return True

    if path.name in EXCLUDE_FILES:
        return True

    if path.suffix in {".pyc", ".log", ".zip"}:
        return True

    return False


with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in PROJECT_ROOT.rglob("*"):
        if should_exclude(path):
            continue

        if path.is_file():
            zf.write(path, path.relative_to(PROJECT_ROOT))

print(f"备份完成：{zip_path}")