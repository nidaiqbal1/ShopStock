import re
import tempfile
from pathlib import Path

from flask import (Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for)

from models.models import db, set_setting, get_setting
from routes.auth import owner_required
from services import backup_service as bs
from utils import clean

bp = Blueprint("backup", __name__)


@bp.route("/backup")
@owner_required
def index():
    return render_template("backup.html", backups=bs.list_backups(current_app), folder=get_setting("backup_folder", ""))


@bp.route("/backup/create", methods=["POST"])
@owner_required
def create():
    try:
        p = bs.create_backup(current_app, "manual")
        flash(f"Backup created: {p.name}", "success")
    except (ValueError, OSError) as e:
        flash(str(e), "error")
    return redirect(url_for("backup.index"))


@bp.route("/backup/download-now")
@owner_required
def download_now():
    p = bs.create_backup(current_app, "manual")
    return send_file(p, as_attachment=True, download_name=p.name)


@bp.route("/backup/download/<name>")
@owner_required
def download(name):
    if not bs.NAME_RE.match(name):
        return redirect(url_for("backup.index"))
    path = bs.backup_dir(current_app) / name
    if not path.exists():
        flash("Backup file not found.", "error")
        return redirect(url_for("backup.index"))
    return send_file(path, as_attachment=True, download_name=name)


@bp.route("/backup/folder", methods=["POST"])
@owner_required
def folder():
    f = clean(request.form.get("folder"), 300)
    if f and not Path(f).is_dir():
        flash("That folder does not exist. Create it (or plug in the USB drive) and try again.", "error")
    else:
        set_setting("backup_folder", f)
        db.session.commit()
        flash("Extra backup folder saved." if f else "Extra backup folder cleared.", "success")
    return redirect(url_for("backup.index"))


@bp.route("/backup/restore", methods=["POST"])
@owner_required
def restore():
    name, upload = request.form.get("name", ""), request.files.get("file")
    try:
        if upload and upload.filename:
            tmp = Path(tempfile.mkdtemp()) / "upload.db"
            upload.save(tmp)
            source = tmp
        elif bs.NAME_RE.match(name) and (bs.backup_dir(current_app) / name).exists():
            source = bs.backup_dir(current_app) / name
        else:
            raise ValueError("Choose a backup to restore.")
        bs.restore(current_app, source)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("backup.index"))
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    flash("Backup restored. Please log in again. (A safety copy of the previous data was saved first.)", "success")
    return redirect(url_for("auth.login"))
