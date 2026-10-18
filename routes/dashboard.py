from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_

from models.models import Customer, Product, Supplier, db, set_setting
from routes.auth import login_required, owner_required
from services import report_service as rs
from utils import clean

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    if not g.user.is_owner:
        return redirect(url_for("sales.pos"))
    stats, charts = rs.dashboard_data()
    return render_template("dashboard.html", stats=stats, charts=charts, insights=rs.insights(), low=rs.low_stock_products(6))


@bp.route("/search")
@login_required
def search():
    q = clean(request.args.get("q"), 80)
    res = {"products": [], "customers": [], "suppliers": []}
    if q:
        like = f"%{q}%"
        res["products"] = Product.query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like))).limit(25).all()
        res["customers"] = Customer.query.filter(or_(Customer.name.ilike(like), Customer.phone.ilike(like))).limit(25).all()
        if g.user.is_owner:
            res["suppliers"] = Supplier.query.filter(or_(Supplier.name.ilike(like), Supplier.phone.ilike(like))).limit(25).all()
    return render_template("search.html", q=q, res=res)


@bp.route("/settings", methods=["GET", "POST"])
@owner_required
def settings():
    if request.method == "POST":
        try:
            name = clean(request.form.get("shop_name"), 100)
            if not name:
                raise ValueError("Shop name is required.")
            low = request.form.get("low_stock_default", "5").strip()
            if not low.replace(".", "", 1).isdigit():
                raise ValueError("Low-stock default must be a number.")
            for k, mx in (("owner_name", 100), ("phone", 30), ("address", 200), ("email", 120), ("currency", 10)):
                set_setting(k, clean(request.form.get(k), mx) or ("Rs." if k == "currency" else ""))
            set_setting("invoice_lang", "ur" if request.form.get("invoice_lang") == "ur" else "en")
            set_setting("shop_name", name)
            set_setting("low_stock_default", low)
            db.session.commit()
            flash("Settings saved.", "success")
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        return redirect(url_for("dashboard.settings"))
    return render_template("settings.html")
