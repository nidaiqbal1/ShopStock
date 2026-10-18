import secrets
import time
from functools import wraps

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for

from models.models import User, db

bp = Blueprint("auth", __name__)
_failed = {}  # ip -> [timestamps]  (simple brute-force throttle)


def _wants_json():
    return request.is_json or request.path.startswith(("/ai/ask", "/sales/pos/checkout"))


def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if g.get("user") is None:
            if _wants_json():
                return jsonify(ok=False, error="Please log in again."), 401
            return redirect(url_for("auth.login", next=request.path if request.method == "GET" else None))
        return view(*a, **kw)
    return wrapper


def owner_required(view):
    """Only the shop owner (not cashiers) may use this page."""
    @wraps(view)
    def wrapper(*a, **kw):
        if g.get("user") is None:
            if _wants_json():
                return jsonify(ok=False, error="Please log in again."), 401
            return redirect(url_for("auth.login", next=request.path if request.method == "GET" else None))
        if not g.user.is_owner:
            if _wants_json():
                return jsonify(ok=False, error="Only the shop owner can do this."), 403
            flash("Only the shop owner can open that page.", "error")
            return redirect(url_for("sales.pos"))
        return view(*a, **kw)
    return wrapper


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        recent = [t for t in _failed.get(ip, []) if time.time() - t < 300]
        _failed[ip] = recent
        if len(recent) >= 5:
            flash("Too many failed attempts. Please wait a few minutes and try again.", "error")
            return render_template("login.html"), 429
        user = User.query.filter_by(username=(request.form.get("username") or "").strip()).first()
        if user and user.is_active and user.check_password(request.form.get("password") or ""):
            _failed.pop(ip, None)
            nxt, lang = _safe_next(request.args.get("next")), session.get("lang")
            session.clear()
            session["uid"] = user.id
            session["csrf"] = secrets.token_hex(16)
            if lang:
                session["lang"] = lang
            session.permanent = True
            return redirect(nxt or url_for("dashboard.index"))
        recent.append(time.time())
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/account")
@login_required
def account():
    return render_template("account.html")


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    cur, new, conf = (request.form.get(k, "") for k in ("current", "new", "confirm"))
    if not g.user.check_password(cur):
        flash("Current password is incorrect.", "error")
    elif len(new) < 8:
        flash("New password must be at least 8 characters.", "error")
    elif new == "admin123" or new == cur:
        flash("Please choose a different, new password.", "error")
    elif new != conf:
        flash("New passwords do not match.", "error")
    else:
        g.user.set_password(new)
        g.user.must_change_password = False
        db.session.commit()
        flash("Password changed.", "success")
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.account"))


@bp.route("/lang/<code>")
def set_language(code):
    if code in ("en", "ur"):
        session["lang"] = code
    ref = request.referrer or ""
    return redirect(ref if ref.startswith(request.host_url) else url_for("dashboard.index"))
