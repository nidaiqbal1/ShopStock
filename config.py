"""ShopStock configuration. Secrets come from environment variables / .env, never from source."""
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # True when running as the packaged Windows .exe
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))  # templates/static live here
BASE_DIR = Path(__file__).resolve().parent


def _data_dir():
    """Where the database, backups and .env live. Packaged app: %LOCALAPPDATA%\\ShopStock (always writable)."""
    env = os.environ.get("SHOPSTOCK_DATA")
    if env:
        return Path(env)
    if FROZEN:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ShopStock"
    return BASE_DIR


DATA_DIR = _data_dir()
INSTANCE_DIR = DATA_DIR / "instance"
BACKUP_DIR = DATA_DIR / "backups"
for _d in (INSTANCE_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

try:  # optional: load variables from a local .env file
    from dotenv import load_dotenv
    load_dotenv(DATA_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


def _secret_key():
    """Use SECRET_KEY if provided, otherwise generate one once and keep it in instance/."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    key_file = INSTANCE_DIR / "secret.key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + (INSTANCE_DIR / "shopstock.db").as_posix())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # allows restoring large backups
    BACKUP_DIR = str(BACKUP_DIR)
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
