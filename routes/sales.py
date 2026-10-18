from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from models.models import Customer, Product, Sale, SaleItem, SaleReturn, SaleReturnItem, db, get_setting
from routes.auth import login_required, owner_required
from services.inventory_service import change_stock
from services.invoice_service import build_invoice_pdf
from services.whatsapp_service import chat_link, invoice_message
from utils import clean, parse_date, parse_float

bp = Blueprint("sales", __name__)
CREDIT = "Credit/Udhaar"
METHODS = ["Cash", "Bank", "Easypaisa", "JazzCash", CREDIT]


def next_invoice_no():
    base = f"INV-{date.today():%Y%m%d}"
    n = Sale.query.filter(Sale.invoice_no.like(base + "-%")).count() + 1
    while Sale.query.filter_by(invoice_no=f"{base}-{n:04d}").first():
        n += 1
    return f"{base}-{n:04d}"


@bp.route("/sales/pos")
@login_required
def pos():
    return render_template("pos.html", customers=Customer.query.order_by(Customer.name).all(), methods=METHODS, credit=CREDIT)


@bp.route("/sales/pos/checkout", methods=["POST"])
@login_required
def checkout():
    d = request.get_json(silent=True) or {}
    try:
        lines = d.get("items") or []
        if not isinstance(lines, list) or not lines:
            raise ValueError("The cart is empty.")
        method = d.get("payment_method")
        if method not in METHODS:
            raise ValueError("Please select a payment method.")
        cust = None
        if d.get("customer_id"):
            cust = db.session.get(Customer, int(d["customer_id"]))
            if cust is None:
                raise ValueError("Customer not found.")
        merged = {}
        for l in lines:
            pid = int(l["product_id"])
            merged[pid] = merged.get(pid, 0) + parse_float(l.get("qty"), "Quantity", minimum=0.001)
        sale = Sale(invoice_no=next_invoice_no(), customer=cust, date=date.today(), payment_method=method)
        subtotal = cost = 0.0
        for pid, qty in merged.items():
            p = db.session.get(Product, pid)
            if p is None:
                raise ValueError("A product in the cart no longer exists.")
            sale.items.append(SaleItem(product=p, product_name=p.name, quantity=qty, purchase_price=p.purchase_price,
                                       selling_price=p.selling_price, subtotal=round(qty * p.selling_price, 2),
                                       profit=round(qty * (p.selling_price - p.purchase_price), 2)))
            subtotal += qty * p.selling_price
            cost += qty * p.purchase_price
            change_stock(p, qty, "out", "sale", reference=sale.invoice_no)
        subtotal = round(subtotal, 2)
        discount = parse_float(d.get("discount"), "Discount", required=False)
        if discount > subtotal:
            raise ValueError("Discount cannot be more than the subtotal.")
        total = round(subtotal - discount, 2)
        paid_raw = d.get("paid")
        if paid_raw in (None, ""):
            paid = 0.0 if method == CREDIT else total
        else:
            paid = parse_float(paid_raw, "Paid amount")
        if paid > total:
            raise ValueError("Paid amount cannot be more than the total.")
        remaining = round(total - paid, 2)
        if remaining > 0 and cust is None:
            raise ValueError("Select a customer for credit or partially paid sales.")
        sale.subtotal, sale.discount, sale.total = subtotal, discount, total
        sale.paid, sale.remaining = paid, remaining
        sale.profit = round(total - cost, 2)
        db.session.add(sale)
        db.session.commit()
        return jsonify(ok=True, sale_id=sale.id, invoice_no=sale.invoice_no, url=url_for("sales.view_sale", sid=sale.id))
    except ValueError as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 400
    except (KeyError, TypeError):
        db.session.rollback()
        return jsonify(ok=False, error="Invalid cart data."), 400
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(ok=False, error="Could not save the sale. Nothing was changed."), 500


@bp.route("/sales")
@login_required
def list_sales():
    q = clean(request.args.get("q"), 60)
    method = request.args.get("method", "")
    try:
        start, end = parse_date(request.args.get("start")), parse_date(request.args.get("end"))
    except ValueError as e:
        flash(str(e), "error")
        start = end = None
    query = Sale.query.outerjoin(Customer)
    if q:
        query = query.filter(or_(Sale.invoice_no.ilike(f"%{q}%"), Customer.name.ilike(f"%{q}%")))
    if method in METHODS:
        query = query.filter(Sale.payment_method == method)
    if start:
        query = query.filter(Sale.date >= start)
    if end:
        query = query.filter(Sale.date <= end)
    sales = query.order_by(Sale.id.desc()).limit(500).all()
    return render_template("sales.html", sales=sales, q=q, method=method, methods=METHODS,
                           start=request.args.get("start", ""), end=request.args.get("end", ""),
                           total=sum(s.total for s in sales if s.status == "completed"), profit=sum(s.profit for s in sales if s.status == "completed"))


@bp.route("/sales/<int:sid>")
@login_required
def view_sale(sid):
    s = db.get_or_404(Sale, sid)
    return render_template("sale_detail.html", s=s, wa=bool(s.customer and chat_link(s.customer.phone)))


@bp.route("/sales/<int:sid>/invoice.pdf")
@login_required
def invoice_pdf(sid):
    s = db.get_or_404(Sale, sid)
    lang = request.args.get("lang") if request.args.get("lang") in ("en", "ur") else get_setting("invoice_lang", "en")
    return send_file(build_invoice_pdf(s, lang), mimetype="application/pdf", as_attachment=request.args.get("inline") != "1",
                     download_name=f"{s.invoice_no}{'-ur' if lang == 'ur' else ''}.pdf")


@bp.route("/sales/<int:sid>/receipt")
@login_required
def receipt(sid):
    """80mm thermal-printer receipt. Add ?print=1 to open the print dialog automatically."""
    return render_template("receipt.html", s=db.get_or_404(Sale, sid), auto=request.args.get("print") == "1")


@bp.route("/sales/<int:sid>/void", methods=["POST"])
@owner_required
def void_sale(sid):
    s = db.get_or_404(Sale, sid)
    try:
        if s.status == "voided":
            raise ValueError("This sale is already voided.")
        if s.returned_total > 0:
            raise ValueError("This sale already has returned items and cannot be voided.")
        if s.customer and s.customer.balance - s.remaining < -0.004:
            raise ValueError("Cannot void: the customer has already paid towards this credit. Use Return items instead.")
        for i in s.items:
            if i.product:
                change_stock(i.product, i.quantity, "in", "void sale", reference=s.invoice_no)
        s.status = "voided"
        s.void_reason = clean(request.form.get("reason")) or None
        db.session.commit()
        flash(f"Sale {s.invoice_no} voided and stock restored.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("sales.view_sale", sid=sid))


@bp.route("/sales/<int:sid>/return", methods=["POST"])
@owner_required
def return_items(sid):
    s = db.get_or_404(Sale, sid)
    try:
        if s.status != "completed":
            raise ValueError("Voided sales cannot have returns.")
        factor = (s.subtotal - s.discount) / s.subtotal if s.subtotal > 0 else 1.0
        sret = SaleReturn(sale=s, note=clean(request.form.get("note")) or None)
        refund = cost = 0.0
        for item in s.items:
            qty = parse_float(request.form.get(f"qty_{item.id}"), f"Return quantity for {item.product_name}", required=False)
            if qty <= 0:
                continue
            if qty > item.returnable_qty + 1e-9:
                raise ValueError(f"You can return at most {item.returnable_qty:g} of {item.product_name}.")
            amount = round(qty * item.selling_price * factor, 2)
            sret.items.append(SaleReturnItem(sale_item=item, quantity=qty, amount=amount))
            item.returned_qty = round(item.returned_qty + qty, 3)
            refund += amount
            cost += qty * item.purchase_price
            if item.product:
                change_stock(item.product, qty, "in", "sales return", reference=s.invoice_no)
        refund = round(refund, 2)
        if refund <= 0:
            raise ValueError("Enter the quantity of at least one item to return.")
        credit = round(min(s.remaining, refund, max(s.customer.balance, 0) if s.customer else 0), 2)
        cash = round(refund - credit, 2)
        if cash > s.paid + 0.004:
            raise ValueError("Cannot process this return automatically because the customer already settled part of this credit through khata.")
        s.total = max(round(s.total - refund, 2), 0)
        s.remaining = round(s.remaining - credit, 2)
        s.paid = max(round(s.total - s.remaining, 2), 0)
        s.profit = round(s.profit - (refund - cost), 2)
        s.returned_total = round(s.returned_total + refund, 2)
        sret.refund_amount, sret.credit_applied, sret.cash_refunded = refund, credit, cash
        db.session.add(sret)
        db.session.commit()
        flash(f"Return recorded: {refund:,.2f} (cash refund {cash:,.2f}, deducted from khata {credit:,.2f}). Stock updated.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("sales.view_sale", sid=sid))


def remove_sale(s, restock=True):
    """Permanently delete a sale (and its returns). Optionally put the unreturned items back in stock."""
    if restock and s.status == "completed":
        for i in s.items:
            back = round(i.quantity - i.returned_qty, 3)
            if i.product and back > 0:
                change_stock(i.product, back, "in", "sale deleted", reference=s.invoice_no)
    db.session.delete(s)


@bp.route("/sales/<int:sid>/delete", methods=["POST"])
@owner_required
def delete_sale(sid):
    s = db.get_or_404(Sale, sid)
    inv = s.invoice_no
    try:
        remove_sale(s, restock=request.form.get("restock", "1") == "1")
        db.session.commit()
        flash(f"Sale {inv} deleted.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("sales.view_sale", sid=sid))
    return redirect(url_for("sales.list_sales"))
