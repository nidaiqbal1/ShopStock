"""ShopStock - Smart Shop & Inventory Management.  Run with:  python app.py"""
import os
import secrets
import threading
import webbrowser

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from config import RESOURCE_DIR, Config
from models.models import DEFAULT_SETTINGS, Setting, User, all_settings, db
from utils import fmt_qty, money

OPEN_WHEN_PASSWORD_MUST_CHANGE = {"auth.account", "auth.change_password", "auth.logout", "auth.set_language", "static"}


def create_app(config_overrides=None):
    app = Flask(__name__, template_folder=str(RESOURCE_DIR / "templates"), static_folder=str(RESOURCE_DIR / "static"))
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    db.init_app(app)

    from routes import (ai, auth, backup, customers, dashboard, exports, expenses, products, purchases,
                        reports, sales, suppliers, users, whatsapp)
    for m in (auth, dashboard, products, sales, customers, suppliers, purchases, expenses, reports, whatsapp, ai,
              users, backup, exports):
        app.register_blueprint(m.bp)
    app.register_blueprint(customers.khata_bp)

    from services.backup_service import maybe_daily_backup
    from services.i18n import translate

    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["qty"] = fmt_qty

    @app.before_request
    def load_user_and_check_csrf():
        g.user = db.session.get(User, session["uid"]) if session.get("uid") else None
        if g.user is not None and not g.user.is_active:
            session.clear()
            g.user = None
        if request.method == "POST":
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            expected = session.get("csrf")
            if not expected or not sent or not secrets.compare_digest(sent, expected):
                return _error(400, "Your session expired or the form was invalid. Please go back, refresh and try again.")
        if g.user is not None:
            if g.user.must_change_password and request.endpoint not in OPEN_WHEN_PASSWORD_MUST_CHANGE:
                return redirect(url_for("auth.account"))
            maybe_daily_backup(app)

    @app.context_processor
    def inject():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        token = session["csrf"]
        lang = session.get("lang", "en")
        user = g.get("user")
        shop = all_settings() if user else dict(DEFAULT_SETTINGS)
        return {"shop": shop, "csrf_token": lambda: token, "currency": shop["currency"], "lang": lang,
                "dir": "rtl" if lang == "ur" else "ltr", "t": lambda s: translate(s, lang),
                "is_owner": bool(user and user.is_owner),
                "csrf_input": lambda: Markup(f'<input type="hidden" name="csrf_token" value="{token}">')}

    def _error(code, message=None):
        if request.is_json or request.path.startswith(("/ai/ask", "/sales/pos/checkout", "/products/api")):
            return jsonify(ok=False, error=message or "Something went wrong."), code
        if code == 404:
            return render_template("404.html"), 404
        return render_template("500.html", message=message), code

    @app.errorhandler(HTTPException)
    def http_error(e):
        return _error(e.code, e.description if e.code != 500 else None)

    @app.errorhandler(Exception)
    def unhandled(e):
        db.session.rollback()
        app.logger.exception("Unhandled error: %s", e)
        return _error(500, "Something went wrong on our side. Your data was not changed.")

    @app.errorhandler(SQLAlchemyError)
    def db_error(e):
        db.session.rollback()
        app.logger.exception("Database error: %s", e)
        return _error(500, "A database error occurred. Your last change was not saved.")

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    with app.app_context():
        from services.migrate import upgrade
        upgrade()  # create tables + add columns that older versions lack
        for k, v in DEFAULT_SETTINGS.items():  # configuration defaults only - no business data
            if db.session.get(Setting, k) is None:
                db.session.add(Setting(key=k, value=v))
        if User.query.count() == 0:
            admin = User(username=app.config["DEFAULT_ADMIN_USERNAME"], full_name="Administrator", role="owner")
            admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
            db.session.add(admin)
            db.session.flush()
        for u in User.query.all():  # anyone still on the published default password must choose a new one
            if u.check_password(app.config["DEFAULT_ADMIN_PASSWORD"]):
                u.must_change_password = True
        db.session.commit()
        maybe_daily_backup(app)
    return app


def main():
    app = create_app()
    host = os.environ.get("SHOPSTOCK_HOST", "127.0.0.1")
    port = int(os.environ.get("SHOPSTOCK_PORT", "5000"))
    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(" ShopStock is running.  Open:", url)
    print(" Keep this window open while you use ShopStock.")
    print(" Close this window to stop the program.")
    print("=" * 60)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    except ImportError:  # waitress missing: fall back to Flask's built-in server
        app.run(host=host, port=port)
    except OSError:
        print(f"\nPort {port} is already in use - ShopStock may already be running. Opening {url} ...")


if __name__ == "__main__":
    main()
