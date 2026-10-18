from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from models.models import User, db
from routes.auth import owner_required
from utils import clean

bp = Blueprint("users", __name__)


def _last_owner(u):
    return u.is_owner and u.is_active and User.query.filter_by(role="owner", is_active=True).count() <= 1


@bp.route("/users")
@owner_required
def list_users():
    return render_template("users.html", users=User.query.order_by(User.id).all())


@bp.route("/users/add", methods=["POST"])
@owner_required
def add_user():
    f = request.form
    username, pw = clean(f.get("username"), 60), f.get("password", "")
    try:
        if not username or " " in username:
            raise ValueError("Username is required and cannot contain spaces.")
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            raise ValueError("That username is already taken.")
        if len(pw) < 8:
            raise ValueError("Password must be at least 8 characters.")
        role = f.get("role") if f.get("role") in ("owner", "cashier") else "cashier"
        u = User(username=username, full_name=clean(f.get("full_name"), 120) or username, role=role, must_change_password=True)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        flash(f"User '{username}' created. They must change the password at first login.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("users.list_users"))


@bp.route("/users/<int:uid>/reset", methods=["POST"])
@owner_required
def reset_password(uid):
    u = db.get_or_404(User, uid)
    pw = request.form.get("password", "")
    if len(pw) < 8:
        flash("Password must be at least 8 characters.", "error")
    else:
        u.set_password(pw)
        u.must_change_password = u.id != g.user.id
        db.session.commit()
        flash(f"Password for '{u.username}' reset.", "success")
    return redirect(url_for("users.list_users"))


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@owner_required
def toggle_user(uid):
    u = db.get_or_404(User, uid)
    if u.id == g.user.id or _last_owner(u):
        flash("You cannot deactivate yourself or the last active owner.", "error")
    else:
        u.is_active = not u.is_active
        db.session.commit()
        flash(f"User '{u.username}' {'activated' if u.is_active else 'deactivated'}.", "success")
    return redirect(url_for("users.list_users"))


@bp.route("/users/<int:uid>/role", methods=["POST"])
@owner_required
def set_role(uid):
    u = db.get_or_404(User, uid)
    role = request.form.get("role")
    if role not in ("owner", "cashier"):
        flash("Invalid role.", "error")
    elif role == "cashier" and _last_owner(u):
        flash("There must be at least one active owner.", "error")
    else:
        u.role = role
        db.session.commit()
        flash(f"'{u.username}' is now {role}.", "success")
    return redirect(url_for("users.list_users"))
