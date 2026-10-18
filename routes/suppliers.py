from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from models.models import Payment, Supplier, db
from routes.auth import login_required, owner_required
from routes.customers import PAY_METHODS
from utils import clean, normalize_phone, parse_date, parse_float

bp = Blueprint("suppliers", __name__)


def _fill(s, f):
    name = clean(f.get("name"), 120)
    if not name:
        raise ValueError("Supplier name is required.")
    phone = clean(f.get("phone"), 30)
    if phone and not normalize_phone(phone):
        raise ValueError("Phone number looks invalid.")
    s.name, s.phone = name, phone or None
    s.company, s.email = clean(f.get("company"), 120) or None, clean(f.get("email"), 120) or None
    s.address, s.notes = clean(f.get("address")) or None, clean(f.get("notes"), 1000) or None


@bp.route("/suppliers")
@owner_required
def list_suppliers():
    q = clean(request.args.get("q"), 60)
    query = Supplier.query
    if q:
        query = query.filter(or_(Supplier.name.ilike(f"%{q}%"), Supplier.phone.ilike(f"%{q}%"), Supplier.company.ilike(f"%{q}%")))
    return render_template("suppliers.html", suppliers=query.order_by(Supplier.name).limit(500).all(), q=q)


@bp.route("/suppliers/add", methods=["POST"])
@owner_required
def add_supplier():
    try:
        s = Supplier()
        _fill(s, request.form)
        db.session.add(s)
        db.session.commit()
        flash(f"Supplier '{s.name}' added.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("suppliers.list_suppliers"))


@bp.route("/suppliers/<int:sid>/edit", methods=["POST"])
@owner_required
def edit_supplier(sid):
    s = db.get_or_404(Supplier, sid)
    try:
        _fill(s, request.form)
        db.session.commit()
        flash("Supplier updated.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("suppliers.view_supplier", sid=sid))


@bp.route("/suppliers/<int:sid>")
@owner_required
def view_supplier(sid):
    return render_template("supplier_detail.html", s=db.get_or_404(Supplier, sid), methods=PAY_METHODS)


@bp.route("/suppliers/<int:sid>/delete", methods=["POST"])
@owner_required
def delete_supplier(sid):
    """Delete a supplier with its purchase records and payments. Stock levels are left as they are."""
    s = db.get_or_404(Supplier, sid)
    for p in s.products:
        p.supplier_id = None
    for pur in list(s.purchases):
        db.session.delete(pur)
    for pay in list(s.payments):
        db.session.delete(pay)
    db.session.delete(s)
    db.session.commit()
    flash("Supplier deleted.", "success")
    return redirect(url_for("suppliers.list_suppliers"))


@bp.route("/suppliers/<int:sid>/pay", methods=["POST"])
@owner_required
def pay_supplier(sid):
    s = db.get_or_404(Supplier, sid)
    try:
        amount = parse_float(request.form.get("amount"), "Amount", minimum=0.01)
        if amount > s.payable + 0.004:
            raise ValueError(f"Payment cannot exceed the amount payable ({s.payable:,.2f}).")
        method = request.form.get("method") if request.form.get("method") in PAY_METHODS else "Cash"
        db.session.add(Payment(supplier=s, amount=amount, method=method, note=clean(request.form.get("note")) or None,
                               date=parse_date(request.form.get("date")) or date.today()))
        db.session.commit()
        flash("Payment to supplier recorded.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("suppliers.view_supplier", sid=sid))
