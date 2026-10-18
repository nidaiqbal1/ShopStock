from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.models import Expense, db
from routes.auth import login_required, owner_required
from services import report_service as rs
from utils import clean, parse_date, parse_float

bp = Blueprint("expenses", __name__)
CATEGORIES = ["Rent", "Electricity", "Internet", "Salaries", "Transport", "Maintenance", "Miscellaneous"]


def _fill(e, f):
    title = clean(f.get("title"), 150)
    if not title:
        raise ValueError("Title is required.")
    cat = f.get("category")
    if cat not in CATEGORIES:
        raise ValueError("Select a valid category.")
    e.title, e.category = title, cat
    e.amount = parse_float(f.get("amount"), "Amount", minimum=0.01)
    e.date = parse_date(f.get("date")) or date.today()
    e.description = clean(f.get("description"), 1000) or None


@bp.route("/expenses")
@owner_required
def list_expenses():
    today = date.today()
    cat = request.args.get("category", "")
    query = Expense.query
    if cat in CATEGORIES:
        query = query.filter_by(category=cat)
    return render_template("expenses.html", expenses=query.order_by(Expense.date.desc(), Expense.id.desc()).limit(500).all(),
                           categories=CATEGORIES, cat=cat, today=today, today_total=rs.expenses_total(today, today),
                           month_total=rs.expenses_total(today.replace(day=1), today), total=rs.expenses_total(),
                           breakdown=rs.expense_by_category())


@bp.route("/expenses/add", methods=["POST"])
@owner_required
def add_expense():
    try:
        e = Expense()
        _fill(e, request.form)
        db.session.add(e)
        db.session.commit()
        flash("Expense recorded.", "success")
    except ValueError as err:
        db.session.rollback()
        flash(str(err), "error")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/expenses/<int:eid>/edit", methods=["POST"])
@owner_required
def edit_expense(eid):
    e = db.get_or_404(Expense, eid)
    try:
        _fill(e, request.form)
        db.session.commit()
        flash("Expense updated.", "success")
    except ValueError as err:
        db.session.rollback()
        flash(str(err), "error")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/expenses/<int:eid>/delete", methods=["POST"])
@owner_required
def delete_expense(eid):
    db.session.delete(db.get_or_404(Expense, eid))
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses"))
