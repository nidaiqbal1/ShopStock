from flask import Blueprint, flash, redirect, request, url_for

from models.models import Customer, Sale, db, get_setting
from routes.auth import login_required
from services.whatsapp_service import chat_link, invoice_message, reminder_message

bp = Blueprint("whatsapp", __name__)


def _back(default):
    return redirect(request.referrer or default)


@bp.route("/whatsapp/invoice/<int:sid>")
@login_required
def send_invoice(sid):
    s = db.get_or_404(Sale, sid)
    link = chat_link(s.customer.phone, invoice_message(s, get_setting("shop_name"))) if s.customer else None
    if not link:
        flash("This sale has no customer with a valid phone number.", "error")
        return _back(url_for("sales.view_sale", sid=sid))
    return redirect(link)


@bp.route("/whatsapp/reminder/<int:cid>")
@login_required
def send_reminder(cid):
    c = db.get_or_404(Customer, cid)
    if c.balance <= 0:
        flash(f"{c.name} has no outstanding balance.", "error")
        return _back(url_for("customers.view_customer", cid=cid))
    link = chat_link(c.phone, reminder_message(c, get_setting("shop_name")))
    if not link:
        flash(f"{c.name} has no valid phone number saved.", "error")
        return _back(url_for("customers.view_customer", cid=cid))
    return redirect(link)


@bp.route("/whatsapp/chat/<int:cid>")
@login_required
def chat(cid):
    c = db.get_or_404(Customer, cid)
    link = chat_link(c.phone, f"Assalam-o-Alaikum {c.name},")
    if not link:
        flash(f"{c.name} has no valid phone number saved.", "error")
        return _back(url_for("customers.view_customer", cid=cid))
    return redirect(link)
