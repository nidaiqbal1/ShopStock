from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.models import Product, Purchase, PurchaseItem, Supplier, db
from routes.auth import login_required, owner_required
from services.inventory_service import change_stock
from utils import clean, parse_date, parse_float

bp = Blueprint("purchases", __name__)


@bp.route("/purchases")
@owner_required
def list_purchases():
    items = Purchase.query.order_by(Purchase.id.desc()).limit(300).all()
    return render_template("purchases.html", purchases=items)


@bp.route("/purchases/new", methods=["GET", "POST"])
@owner_required
def new_purchase():
    if request.method == "POST":
        f = request.form
        try:
            supplier = db.session.get(Supplier, f.get("supplier_id", type=int) or 0)
            if supplier is None:
                raise ValueError("Please select a supplier.")
            pids, qtys, prices = f.getlist("product_id"), f.getlist("quantity"), f.getlist("unit_price")
            purchase = Purchase(supplier=supplier, date=parse_date(f.get("date")) or date.today(),
                                notes=clean(f.get("notes"), 500) or None)
            total, seen = 0.0, set()
            for pid, qty, price in zip(pids, qtys, prices):
                if not pid and not qty and not price:
                    continue
                p = db.session.get(Product, int(pid)) if pid.isdigit() else None
                if p is None:
                    raise ValueError("Select a product on every line.")
                if p.id in seen:
                    raise ValueError(f"'{p.name}' appears twice. Combine it into one line.")
                seen.add(p.id)
                q, pr = parse_float(qty, "Quantity", minimum=0.001), parse_float(price, "Purchase price")
                purchase.items.append(PurchaseItem(product=p, product_name=p.name, quantity=q, unit_price=pr, subtotal=round(q * pr, 2)))
                total += q * pr
                change_stock(p, q, "in", "purchase", reference=f"Purchase from {supplier.name}")
                if f.get("update_price"):
                    p.purchase_price = pr
            if not purchase.items:
                raise ValueError("Add at least one product.")
            total = round(total, 2)
            status = f.get("payment_status", "Unpaid")
            paid = {"Paid": total, "Unpaid": 0.0}.get(status)
            if paid is None:
                paid = parse_float(f.get("paid"), "Amount paid", minimum=0.01)
                if paid >= total:
                    raise ValueError("For a partial payment, the amount paid must be less than the total.")
            purchase.total, purchase.paid = total, paid
            purchase.payment_status = "Paid" if paid >= total else ("Unpaid" if paid == 0 else "Partial")
            db.session.add(purchase)
            db.session.commit()
            flash(f"Purchase recorded and stock updated ({purchase.payment_status}).", "success")
            return redirect(url_for("purchases.list_purchases"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
    return render_template("purchase_form.html", suppliers=Supplier.query.order_by(Supplier.name).all(),
                           products=Product.query.order_by(Product.name).all(), today=date.today())


@bp.route("/purchases/<int:pid>/delete", methods=["POST"])
@owner_required
def delete_purchase(pid):
    """Delete a purchase and take its stock back out (as far as stock is still available)."""
    purchase = db.get_or_404(Purchase, pid)
    short = []
    try:
        for i in purchase.items:
            p = i.product
            if p is None:
                continue
            take = min(i.quantity, p.stock_qty)
            if take < i.quantity - 1e-9:
                short.append(p.name)
            if take > 0:
                change_stock(p, take, "out", "purchase deleted", reference=f"Purchase from {purchase.supplier.name}")
        db.session.delete(purchase)
        db.session.commit()
        msg = "Purchase deleted and its stock removed."
        if short:
            msg += " Some of that stock was already sold, so stock was reduced only as far as possible for: " + ", ".join(short) + "."
        flash(msg, "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(request.referrer or url_for("purchases.list_purchases"))
