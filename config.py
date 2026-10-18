
"""ShopStock configuration. Secrets come from environment variables / .env, never from source."""

import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
RESOURCE_DIR = Path(
    getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
)
BASE_DIR = Path(__file__).resolve().parent


def _data_dir():
    """Choose the data directory for the current environment."""
    env = os.environ.get("SHOPSTOCK_DATA")
    if env:
        return Path(env)

    # Vercel's deployment directory is read-only.
    # /tmp is writable but is NOT persistent storage.
    if os.environ.get("VERCEL"):
        return Path("/tmp/shopstock")

    if FROZEN:
        return Path(
            os.environ.get("LOCALAPPDATA") or Path.home()
        ) / "ShopStock"

    return BASE_DIR


DATA_DIR = _data_dir()
INSTANCE_DIR = DATA_DIR / "instance"
BACKUP_DIR = DATA_DIR / "backups"

for _d in (INSTANCE_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# Optional local .env support.
try:
    from dotenv import load_dotenv

    load_dotenv(DATA_DIR / ".env")
except ImportError:
    pass


def _secret_key():
    """Use an environment secret, or persist one for local development."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    if os.environ.get("VERCEL"):
        raise RuntimeError(
            "SECRET_KEY must be configured in Vercel environment variables."
        )

    key_file = INSTANCE_DIR / "secret.key"

    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")

    return key_file.read_text(encoding="utf-8").strip()


class Config:
    SECRET_KEY = _secret_key()

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + (INSTANCE_DIR / "shopstock.db").as_posix(),
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    MAX_CONTENT_LENGTH = 200 * 1024 * 1024

    BACKUP_DIR = str(BACKUP_DIR)

    DEFAULT_ADMIN_USERNAME = os.environ.get(
        "ADMIN_USERNAME", "admin"
    )
    DEFAULT_ADMIN_PASSWORD = os.environ.get(
        "ADMIN_PASSWORD", "admin123"
    )
