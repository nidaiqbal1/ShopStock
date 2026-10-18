"""Database backup / restore for the SQLite file (safe copies using SQLite's own backup API)."""
import re
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from models.models import db, get_setting

NAME_RE = re.compile(r"^shopstock-[a-z-]+-\d{8}-\d{6}\.db$")
REQUIRED_TABLES = {"users", "products", "customers", "sales", "settings"}
_last_check = {"day": None}


def db_file(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    return Path(uri.replace("sqlite:///", "", 1)) if uri.startswith("sqlite:///") else None


def backup_dir(app):
    d = Path(app.config["BACKUP_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_backup(app, tag="manual"):
    src = db_file(app)
    if src is None or not src.exists():
        raise ValueError("Backup is only available for the SQLite database.")
    dest = backup_dir(app) / f"shopstock-{tag}-{datetime.now():%Y%m%d-%H%M%S}.db"
    s, d = sqlite3.connect(str(src)), sqlite3.connect(str(dest))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    _copy_extra(dest)
    return dest


def _copy_extra(path):
    """Also copy to the owner's chosen folder (USB drive, OneDrive...) if one is set."""
    try:
        folder = (get_setting("backup_folder", "") or "").strip()
        if folder and Path(folder).is_dir():
            shutil.copy2(path, Path(folder) / path.name)
    except Exception:  # never break the app because an external drive is missing
        pass


def list_backups(app):
    out = []
    for f in sorted(backup_dir(app).glob("shopstock-*.db"), reverse=True):
        if NAME_RE.match(f.name):
            st = f.stat()
            out.append({"name": f.name, "size_kb": round(st.st_size / 1024), "when": datetime.fromtimestamp(st.st_mtime)})
    return out


def rotate(app, keep=14):
    autos = [b for b in list_backups(app) if "-auto-" in b["name"]]
    for b in autos[keep:]:
        (backup_dir(app) / b["name"]).unlink(missing_ok=True)


def maybe_daily_backup(app):
    """Once per day (per process start) make an automatic backup if today's doesn't exist yet."""
    today = date.today()
    if _last_check["day"] == today:
        return
    _last_check["day"] = today
    stamp = f"-auto-{today:%Y%m%d}-"
    if not any(stamp in b["name"] for b in list_backups(app)):
        try:
            create_backup(app, "auto")
            rotate(app)
        except Exception:
            app.logger.exception("Automatic backup failed")


def validate_db(path):
    try:
        con = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("The backup file is damaged.")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not REQUIRED_TABLES <= tables:
                raise ValueError("This file is not a ShopStock database.")
            if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] < 1:
                raise ValueError("This backup has no user accounts.")
        finally:
            con.close()
    except sqlite3.DatabaseError:
        raise ValueError("This file is not a valid ShopStock database.")


def restore(app, path):
    """Replace the live database with `path` (after validating it and taking a safety backup)."""
    from services.migrate import upgrade
    validate_db(path)
    target = db_file(app)
    create_backup(app, "before-restore")
    db.session.remove()
    db.engine.dispose()
    shutil.copyfile(path, target)
    for ext in ("-wal", "-shm"):
        Path(str(target) + ext).unlink(missing_ok=True)
    upgrade()  # bring older backups up to the current schema
