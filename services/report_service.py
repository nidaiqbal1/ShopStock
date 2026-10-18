"""Business queries used by the dashboard, reports, khata statements and the AI assistant."""
from datetime import date, datetime, timedelta
from io import BytesIO
from xml.sax.saxutils import escape

from sqlalchemy import func

from models.models import (db, Customer, Expense, Payment, Product, Purchase, Sale, SaleItem,
                           Supplier, all_settings)
from utils import fmt_qty, money


def _r(x):
    return round(float(x or 0), 2)


# ---------------------------------------------------------------- core metrics
def sales_totals(start, end):
    t, p, d, c = db.session.query(
        func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(Sale.profit), 0),
        func.coalesce(func.sum(Sale.discount), 0), func.count(Sale.id)
    ).filter(Sale.date >= start, Sale.date <= end, Sale.status == "completed").one()
    return {"total": _r(t), "profit": _r(p), "discount": _r(d), "count": int(c)}


def expenses_total(start=None, end=None):
    q = db.session.query(func.coalesce(func.sum(Expense.amount), 0))
    if start:
        q = q.filter(Expense.date >= start)
    if end:
        q = q.filter(Expense.date <= end)
    return _r(q.scalar())


def expense_by_category(start=None, end=None):
    q = db.session.query(Expense.category, func.sum(Expense.amount))
    if start:
        q = q.filter(Expense.date >= start)
    if end:
        q = q.filter(Expense.date <= end)
    rows = q.group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    return [(c, _r(a)) for c, a in rows]


def top_products(start=None, end=None, limit=5):
    net = SaleItem.quantity - SaleItem.returned_qty
    q = db.session.query(SaleItem.product_id, func.max(SaleItem.product_name),
                         func.sum(net).label("qty"), func.sum(SaleItem.subtotal * net / SaleItem.quantity)) \
        .join(Sale, Sale.id == SaleItem.sale_id).filter(Sale.status == "completed")
    if start:
        q = q.filter(Sale.date >= start)
    if end:
        q = q.filter(Sale.date <= end)
    rows = q.group_by(SaleItem.product_id).order_by(func.sum(net).desc()).limit(limit).all()
    return [{"name": n, "qty": _r(qty), "revenue": _r(rev)} for _, n, qty, rev in rows]


def receivables():
    out = [(c, c.balance) for c in Customer.query.all()]
    return sorted([(c, b) for c, b in out if b > 0.004], key=lambda x: -x[1])


def payables():
    out = [(s, s.payable) for s in Supplier.query.all()]
    return sorted([(s, b) for s, b in out if b > 0.004], key=lambda x: -x[1])


def inventory_summary():
    products = Product.query.all()
    return {
        "products": len(products),
        "total_qty": _r(sum(p.stock_qty for p in products)),
        "value": _r(sum(p.stock_value for p in products)),
        "retail_value": _r(sum(p.stock_qty * p.selling_price for p in products)),
        "low": sum(1 for p in products if p.is_low and p.stock_qty > 0),
        "out": sum(1 for p in products if p.stock_qty <= 0),
        "ok": sum(1 for p in products if not p.is_low),
    }


def low_stock_products(limit=None):
    q = Product.query.filter(Product.stock_qty <= Product.min_stock).order_by(Product.stock_qty)
    return q.limit(limit).all() if limit else q.all()


def sales_daily(start, end):
    rows = db.session.query(Sale.date, func.count(Sale.id), func.sum(Sale.total),
                            func.sum(Sale.discount), func.sum(Sale.profit)) \
        .filter(Sale.date >= start, Sale.date <= end, Sale.status == "completed").group_by(Sale.date).order_by(Sale.date).all()
    return [(d, c, _r(t), _r(di), _r(p)) for d, c, t, di, p in rows]


def customer_ledger(c):
    rows = [(s.date, s.created_at, f"Credit sale {s.invoice_no}", s.remaining, 0.0)
            for s in c.sales if s.remaining > 0 and s.status == "completed"]
    rows += [(p.date, p.created_at, f"Payment received ({p.method})" + (f" - {p.note}" if p.note else ""), 0.0, p.amount)
             for p in c.payments]
    rows.sort(key=lambda r: (r[0], r[1]))
    out, bal = [], 0.0
    for d, _, desc, debit, credit in rows:
        bal = round(bal + debit - credit, 2)
        out.append({"date": d, "desc": desc, "debit": debit, "credit": credit, "balance": bal})
    return out


# ---------------------------------------------------------------- dashboard
def dashboard_data():
    today = date.today()
    t = sales_totals(today, today)
    inv = inventory_summary()
    start = today - timedelta(days=29)
    daily = sales_daily(start, today)
    top = top_products(limit=5)
    exp = expense_by_category()
    stats = {
        "products": inv["products"], "stock_qty": inv["total_qty"], "today_sales": t["total"],
        "today_profit": t["profit"], "receivables": _r(sum(b for _, b in receivables())),
        "expenses": expenses_total(), "low_stock": inv["low"] + inv["out"],
        "customers": Customer.query.count(),
    }
    charts = {
        "sales_labels": [d.strftime("%d %b") for d, *_ in daily],
        "sales_values": [r[2] for r in daily], "profit_values": [r[4] for r in daily],
        "top_labels": [p["name"] for p in top], "top_values": [p["qty"] for p in top],
        "exp_labels": [c for c, _ in exp], "exp_values": [a for _, a in exp],
        "stock": [inv["ok"], inv["low"], inv["out"]] if inv["products"] else [],
    }
    return stats, charts


def insights():
    """Plain-language insights, computed only from recorded data."""
    out, today = [], date.today()
    top = top_products(limit=1)
    if top:
        out.append(("bi-trophy", f"Best-selling product: {top[0]['name']} ({fmt_qty(top[0]['qty'])} sold)."))
    rec = receivables()
    if rec:
        out.append(("bi-person-exclamation", f"Highest outstanding customer: {rec[0][0].name} owes {money(rec[0][1])}."))
    low = low_stock_products()
    if low:
        names = ", ".join(p.name for p in low[:3]) + ("..." if len(low) > 3 else "")
        out.append(("bi-exclamation-triangle", f"{len(low)} product(s) at or below minimum stock: {names}."))
    w1 = sales_totals(today - timedelta(days=6), today)["total"]
    w0 = sales_totals(today - timedelta(days=13), today - timedelta(days=7))["total"]
    if w0 > 0:
        ch = (w1 - w0) / w0 * 100
        out.append(("bi-graph-up-arrow" if ch >= 0 else "bi-graph-down-arrow",
                    f"Sales trend: {money(w1)} in the last 7 days, {abs(ch):.0f}% {'up' if ch >= 0 else 'down'} from the 7 days before."))
    ms = today.replace(day=1)
    lm_end = ms - timedelta(days=1)
    e1, e0 = expenses_total(ms, today), expenses_total(lm_end.replace(day=1), lm_end)
    if e0 > 0:
        ch = (e1 - e0) / e0 * 100
        out.append(("bi-wallet2", f"Expense trend: {money(e1)} this month, {abs(ch):.0f}% {'higher' if ch >= 0 else 'lower'} than last month."))
    m = sales_totals(ms, today)
    if m["count"]:
        out.append(("bi-cash-coin", f"Profit this month: {money(m['profit'])} from {money(m['total'])} in sales."))
    return out


# ---------------------------------------------------------------- reports
def resolve_range(period, start_s, end_s):
    today = date.today()
    if period == "daily":
        return today, today
    if period == "weekly":
        return today - timedelta(days=6), today
    if period == "monthly":
        return today.replace(day=1), today
    from utils import parse_date
    s, e = parse_date(start_s, "Start date"), parse_date(end_s, "End date")
    s, e = s or today.replace(day=1), e or today
    if s > e:
        raise ValueError("Start date must be before end date.")
    return s, e


REPORT_TYPES = {"sales": "Sales Report", "profit": "Profit Report", "expenses": "Expense Report",
                "inventory": "Inventory Report", "receivables": "Customer Receivables",
                "payables": "Supplier Payables"}


def get_report(kind, start, end):
    rng = f"{start:%d %b %Y} to {end:%d %b %Y}"
    title = REPORT_TYPES[kind]
    if kind == "sales":
        rows = sales_daily(start, end)
        t = sales_totals(start, end)
        return dict(title=title, subtitle=rng, headers=["Date", "Invoices", "Sales", "Discount", "Profit"],
                    rows=[[f"{d:%d %b %Y}", c, money(tt), money(di), money(p)] for d, c, tt, di, p in rows],
                    num_cols=[1, 2, 3, 4],
                    summary=[("Invoices", t["count"]), ("Total sales", money(t["total"])),
                             ("Discounts given", money(t["discount"])), ("Gross profit", money(t["profit"]))])
    if kind == "profit":
        sales = {d: (tt, p) for d, _, tt, _, p in sales_daily(start, end)}
        exps = dict(db.session.query(Expense.date, func.sum(Expense.amount))
                    .filter(Expense.date >= start, Expense.date <= end).group_by(Expense.date).all())
        days = sorted(set(sales) | set(exps))
        rows = [[f"{d:%d %b %Y}", money(sales.get(d, (0, 0))[0]), money(sales.get(d, (0, 0))[1]),
                 money(exps.get(d, 0)), money(sales.get(d, (0, 0))[1] - (exps.get(d) or 0))] for d in days]
        gp = sum(v[1] for v in sales.values())
        ex = sum(exps.values())
        return dict(title=title, subtitle=rng, headers=["Date", "Sales", "Gross profit", "Expenses", "Net profit"],
                    rows=rows, num_cols=[1, 2, 3, 4],
                    summary=[("Gross profit", money(gp)), ("Expenses", money(ex)), ("Net profit", money(gp - ex))])
    if kind == "expenses":
        items = Expense.query.filter(Expense.date >= start, Expense.date <= end).order_by(Expense.date).all()
        by_cat = expense_by_category(start, end)
        return dict(title=title, subtitle=rng, headers=["Date", "Title", "Category", "Amount"],
                    rows=[[f"{e.date:%d %b %Y}", e.title, e.category, money(e.amount)] for e in items],
                    num_cols=[3],
                    summary=[("Total expenses", money(sum(e.amount for e in items)))] +
                            [(f"  {c}", money(a)) for c, a in by_cat])
    if kind == "inventory":
        ps = Product.query.order_by(Product.name).all()
        inv = inventory_summary()
        return dict(title=title, subtitle=f"As of {date.today():%d %b %Y}",
                    headers=["Product", "SKU", "Stock", "Min", "Cost", "Price", "Value", "Status"],
                    rows=[[p.name, p.sku or "-", f"{fmt_qty(p.stock_qty)} {p.unit or ''}".strip(), fmt_qty(p.min_stock),
                           money(p.purchase_price), money(p.selling_price), money(p.stock_value), p.status] for p in ps],
                    num_cols=[2, 3, 4, 5, 6],
                    summary=[("Products", inv["products"]), ("Inventory value (at cost)", money(inv["value"])),
                             ("Low / out of stock", inv["low"] + inv["out"])])
    if kind == "receivables":
        rec = receivables()
        return dict(title=title, subtitle=f"As of {date.today():%d %b %Y}",
                    headers=["Customer", "Phone", "Total credit", "Payments", "Outstanding"],
                    rows=[[c.name, c.phone or "-", money(c.total_credit), money(c.total_payments), money(b)] for c, b in rec],
                    num_cols=[2, 3, 4], summary=[("Total receivable", money(sum(b for _, b in rec)))])
    pay = payables()
    return dict(title=REPORT_TYPES["payables"], subtitle=f"As of {date.today():%d %b %Y}",
                headers=["Supplier", "Company", "Purchased", "Paid", "Payable"],
                rows=[[s.name, s.company or "-", money(s.total_purchased), money(s.total_paid), money(b)] for s, b in pay],
                num_cols=[2, 3, 4], summary=[("Total payable", money(sum(b for _, b in pay)))])


# ---------------------------------------------------------------- PDF helpers
def _pdf_styles():
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    ss = getSampleStyleSheet()
    return ss, ParagraphStyle("cell", parent=ss["Normal"], fontSize=8.5, leading=10.5)


def pdf_header(story, title, subtitle=None, lang="en"):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer
    from services import pdf_text
    ss, _ = _pdf_styles()
    s = all_settings()
    ur = lang == "ur"
    if ur:
        pdf_text.register_fonts()
    al, f, fb = (2, pdf_text.FONT, pdf_text.FONT_BOLD) if ur else (0, "Helvetica", "Helvetica-Bold")
    sh = pdf_text.shape
    story.append(Paragraph(f"<font color='#1d4ed8'>{escape(sh(s['shop_name']))}</font>",
                           ParagraphStyle("h", parent=ss["Title"], alignment=al, fontName=fb, fontSize=20, spaceAfter=2)))
    info = " | ".join(x for x in (s["address"], s["phone"], s["email"]) if x)
    if info:
        story.append(Paragraph(escape(sh(info)), ParagraphStyle("i", parent=ss["Normal"], alignment=al, fontName=f, textColor=colors.grey, fontSize=9)))
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(sh(title)), ParagraphStyle("t", parent=ss["Heading2"], alignment=al, fontName=fb)))
    if subtitle:
        story.append(Paragraph(escape(sh(subtitle)), ParagraphStyle("st", parent=ss["Normal"], alignment=al, fontName=f)))
    story.append(Spacer(1, 8))


def _footer(canvas, doc):
    from reportlab.lib import colors
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    w = doc.pagesize[0]
    canvas.drawString(doc.leftMargin, 20, "Generated by ShopStock - Smart Shop & Inventory Management")
    canvas.drawRightString(w - doc.rightMargin, 20, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def make_table(headers, rows, num_cols=(), col_widths=None, lang="en"):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    from services import pdf_text
    _, cell = _pdf_styles()
    from reportlab.lib.styles import ParagraphStyle
    ur = lang == "ur"
    font, fbold = "Helvetica", "Helvetica-Bold"
    if ur:  # right-to-left: mirror the column order and shape Urdu text
        pdf_text.register_fonts()
        font, fbold = pdf_text.FONT, pdf_text.FONT_BOLD
        headers = [pdf_text.shape(h) for h in reversed(headers)]
        rows = [[pdf_text.shape(v) for v in reversed(r)] for r in rows]
        col_widths = list(reversed(col_widths)) if col_widths else None
        num_cols = [len(headers) - 1 - i for i in num_cols]
        cell = ParagraphStyle("cellur", parent=cell, fontName=font, alignment=2)
    right = ParagraphStyle("cellr", parent=cell, alignment=2)
    data = [headers] + [[Paragraph(escape(str(v)), right if i in num_cols else cell) for i, v in enumerate(r)] for r in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), fbold), ("FONTSIZE", (0, 0), (-1, 0), 9),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
          ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    for c in num_cols:
        st.append(("ALIGN", (c, 0), (c, 0), "RIGHT"))
    if ur:
        st.append(("ALIGN", (0, 0), (-1, 0), "RIGHT"))
    return t, st


def build_report_pdf(report):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, TableStyle
    ss, _ = _pdf_styles()
    buf = BytesIO()
    size = landscape(A4) if len(report["headers"]) > 5 else A4
    doc = SimpleDocTemplate(buf, pagesize=size, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm, title=report["title"])
    story = []
    pdf_header(story, report["title"], report["subtitle"])
    if report["rows"]:
        t, st = make_table(report["headers"], report["rows"], report["num_cols"])
        t.setStyle(TableStyle(st))
        story.append(t)
    else:
        story.append(Paragraph("No data available for this report.", ss["Normal"]))
    story.append(Spacer(1, 12))
    for label, val in report["summary"]:
        story.append(Paragraph(f"<b>{escape(str(label))}:</b> {escape(str(val))}", ss["Normal"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
