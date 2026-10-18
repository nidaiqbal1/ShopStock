from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from models.models import Customer, Payment, db, get_setting
from routes.auth import login_required, owner_required
from services.invoice_service import build_statement_pdf
from services.report_service import customer_ledger
from services.whatsapp_service import chat_link
from utils import clean, normalize_phone, parse_date, parse_float

bp = Blueprint("customers", __name__)
khata_bp = Blueprint("khata", __name__)
PAY_METHODS = ["Cash", "Bank", "Easypaisa", "JazzCash"]


def _fill(c, f):
    name = clean(f.get("name"), 120)
    if not name:
        raise ValueError("Customer name is required.")
    phone = clean(f.get("phone"), 30)
    if phone and not normalize_phone(phone):
        raise ValueError("Phone number looks invalid (example: 0300 1234567).")
    c.name, c.phone = name, phone or None
    c.address, c.email = clean(f.get("address")) or None, clean(f.get("email"), 120) or None
    c.notes = clean(f.get("notes"), 1000) or None


@bp.route("/customers")
@login_required
def list_customers():
    q = clean(request.args.get("q"), 60)
    query = Customer.query
    if q:
        query = query.filter(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
    return render_template("customers.html", customers=query.order_by(Customer.name).limit(500).all(), q=q)


@bp.route("/customers/add", methods=["POST"])
@login_required
def add_customer():
    try:
        c = Customer()
        _fill(c, request.form)
        db.session.add(c)
        db.session.commit()
        flash(f"Customer '{c.name}' added.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("customers.list_customers"))


@bp.route("/customers/<int:cid>/edit", methods=["POST"])
@login_required
def edit_customer(cid):
    c = db.get_or_404(Customer, cid)
    try:
        _fill(c, request.form)
        db.session.commit()
        flash("Customer updated.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("customers.view_customer", cid=cid))


@bp.route("/customers/<int:cid>")
@login_required
def view_customer(cid):
    c = db.get_or_404(Customer, cid)
    return render_template("customer_detail.html", c=c, wa=bool(chat_link(c.phone)), methods=PAY_METHODS)


@bp.route("/customers/<int:cid>/delete", methods=["POST"])
@owner_required
def delete_customer(cid):
    """Delete a customer. Their sales stay in the reports as walk-in sales; their khata payments are erased."""
    c = db.get_or_404(Customer, cid)
    for sale in c.sales:
        sale.customer_id = None
    for pay in list(c.payments):
        db.session.delete(pay)
    db.session.delete(c)
    db.session.commit()
    flash("Customer deleted.", "success")
    return redirect(url_for("customers.list_customers"))


# ------------------------------------------------------------------ khata
@khata_bp.route("/khata")
@login_required
def index():
    rows = [c for c in Customer.query.order_by(Customer.name).all() if c.total_credit or c.total_payments]
    q = clean(request.args.get("q"), 60).lower()
    if q:
        rows = [c for c in rows if q in c.name.lower() or q in (c.phone or "")]
    rows.sort(key=lambda c: -c.balance)
    return render_template("khata.html", rows=rows, q=q, methods=PAY_METHODS,
                           owing=[c for c in rows if c.balance > 0], total=round(sum(c.balance for c in rows), 2))


@khata_bp.route("/khata/<int:cid>/pay", methods=["POST"])
@login_required
def record_payment(cid):
    c = db.get_or_404(Customer, cid)
    try:
        amount = parse_float(request.form.get("amount"), "Amount", minimum=0.01)
        if amount > c.balance + 0.004:
            raise ValueError(f"Payment cannot exceed the outstanding balance ({c.balance:,.2f}).")
        method = request.form.get("method") if request.form.get("method") in PAY_METHODS else "Cash"
        db.session.add(Payment(customer=c, amount=amount, method=method, note=clean(request.form.get("note")) or None,
                               date=parse_date(request.form.get("date")) or date.today()))
        db.session.commit()
        flash(f"Payment recorded. New balance for {c.name}: {c.balance:,.2f}", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("khata.index"))


@khata_bp.route("/khata/<int:cid>/statement")
@login_required
def statement(cid):
    c = db.get_or_404(Customer, cid)
    return render_template("khata_statement.html", c=c, ledger=customer_ledger(c), wa=bool(chat_link(c.phone)), today=date.today())


@khata_bp.route("/khata/<int:cid>/statement.pdf")
@login_required
def statement_pdf(cid):
    c = db.get_or_404(Customer, cid)
    lang = request.args.get("lang") if request.args.get("lang") in ("en", "ur") else get_setting("invoice_lang", "en")
    return send_file(build_statement_pdf(c, lang), mimetype="application/pdf", as_attachment=True,
                     download_name=f"statement-{c.id}{'-ur' if lang == 'ur' else ''}.pdf")
