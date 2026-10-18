"""PDF invoices and khata statements (ReportLab). English or Urdu (right-to-left)."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services import pdf_text
from services.report_service import _footer, _pdf_styles, customer_ledger, make_table, pdf_header
from utils import fmt_qty, money


class _Lang:
    """Small helper: picks fonts/alignment/text for the chosen language."""
    def __init__(self, lang):
        self.ur = lang == "ur"
        if self.ur:
            pdf_text.register_fonts()
        self.font = pdf_text.FONT if self.ur else "Helvetica"
        self.bold = pdf_text.FONT_BOLD if self.ur else "Helvetica-Bold"
        self.align = 2 if self.ur else 0
        self.lang = "ur" if self.ur else "en"

    def t(self, key):
        return pdf_text.shape(pdf_text.label(key, self.lang))

    def raw(self, key):
        return pdf_text.label(key, self.lang)

    def line(self, key, value):
        """'Label: value' as one string, shaped together so right-to-left order is correct."""
        return pdf_text.shape(f"{self.raw(key)}: {value}")

    def style(self, name="n", size=10, bold=False, color=None, align=None):
        ss, _ = _pdf_styles()
        return ParagraphStyle(name, parent=ss["Normal"], fontName=self.bold if bold else self.font, fontSize=size,
                              leading=size * 1.35, alignment=self.align if align is None else align,
                              textColor=color or colors.black)


def _doc(buf, title):
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                             topMargin=15 * mm, bottomMargin=18 * mm, title=title)


def _totals_table(L, rows, bold_last=True):
    """rows: [(label_key_or_text, value)] - mirrored for right-to-left."""
    data = [[L.t(a), v] for a, v in rows]
    if L.ur:
        data = [[v, a] for a, v in data]
    t = Table(data, colWidths=[40 * mm, 45 * mm] if L.ur else [45 * mm, 40 * mm], hAlign="LEFT" if L.ur else "RIGHT")
    valcol, labcol = (0, 1) if L.ur else (1, 0)
    st = [("FONTNAME", (0, 0), (-1, -1), L.font), ("ALIGN", (valcol, 0), (valcol, -1), "RIGHT" if not L.ur else "LEFT"),
          ("ALIGN", (labcol, 0), (labcol, -1), "RIGHT" if L.ur else "LEFT"), ("TOPPADDING", (0, 0), (-1, -1), 3),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 0.8, colors.HexColor("#1e293b"))]
    if bold_last:
        st.append(("FONTNAME", (0, len(data) - 1), (-1, len(data) - 1), L.bold))
    t.setStyle(TableStyle(st))
    return t


def build_invoice_pdf(sale, lang="en"):
    L = _Lang(lang)
    buf = BytesIO()
    doc = _doc(buf, f"Invoice {sale.invoice_no}")
    story = []
    title = f"{pdf_text.label('INVOICE', L.lang)}  {sale.invoice_no}" + (f"  ({pdf_text.label('VOIDED', L.lang)})" if sale.status == "voided" else "")
    if not L.ur:
        title = f"INVOICE  {sale.invoice_no}" + ("  (VOIDED)" if sale.status == "voided" else "")
    pdf_header(story, title, f"{pdf_text.label('Date', L.lang)}: {sale.date:%d %b %Y}", lang=L.lang)
    c = sale.customer
    story.append(Paragraph(escape(pdf_text.shape(L.raw("Bill to") + ":")), L.style("b", 11, bold=True)))
    if c:
        lines = f"<b>{escape(pdf_text.shape(c.name))}</b>" + "".join(f"<br/>{escape(pdf_text.shape(x))}" for x in (c.phone, c.address) if x)
    else:
        lines = escape(L.t("Walk-in customer"))
    story.append(Paragraph(lines, L.style("c", 10)))
    story.append(Spacer(1, 10))
    ret = pdf_text.label("returned", L.lang)
    rows = [[i.product_name + (f" ({ret} {fmt_qty(i.returned_qty)})" if i.returned_qty else ""), fmt_qty(i.quantity),
             money(i.selling_price), money(i.subtotal)] for i in sale.items]
    t, st = make_table([pdf_text.label(k, L.lang) for k in ("Product", "Qty", "Price", "Total")], rows, [1, 2, 3],
                       col_widths=[85 * mm, 22 * mm, 33 * mm, 38 * mm], lang=L.lang)
    st.append(("ALIGN", (0, 0), (-1, 0), "RIGHT") if L.ur else ("ALIGN", (1, 0), (-1, 0), "RIGHT"))
    t.setStyle(TableStyle(st))
    story += [t, Spacer(1, 10)]
    lines_t = [("Subtotal", money(sale.subtotal)), ("Discount", "- " + money(sale.discount))]
    if sale.returned_total:
        lines_t.append(("Returns", "- " + money(sale.returned_total)))
    story.append(_totals_table(L, lines_t + [("Grand total", money(sale.total))]))
    story.append(Spacer(1, 4))
    story.append(_totals_table(L, [("Paid", money(sale.paid)), ("Remaining", money(sale.remaining))]))
    story.append(Spacer(1, 10))
    method = pdf_text.label(sale.payment_method, L.lang)
    story.append(Paragraph(escape(L.line("Payment method", method)) if L.ur else f"<b>Payment method:</b> {escape(method)}", L.style("p", 10)))
    story.append(Spacer(1, 24))
    thanks = L.t("Thank you") if L.ur else "Thank you for shopping with us! Goods once sold can only be exchanged as per shop policy."
    story.append(Paragraph(f"<i>{escape(thanks)}</i>" if not L.ur else escape(thanks), L.style("f", 10, color=colors.grey, align=1)))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf


def build_statement_pdf(customer, lang="en"):
    L = _Lang(lang)
    buf = BytesIO()
    doc = _doc(buf, f"Statement - {customer.name}")
    story = []
    head = f"{pdf_text.label('STATEMENT', L.lang)} - {customer.name}" if L.ur else f"Khata Statement - {customer.name}"
    pdf_header(story, head, f"{pdf_text.label('Phone', L.lang)}: {customer.phone or '-'}", lang=L.lang)
    led = customer_ledger(customer)

    def desc(d):
        if not L.ur:
            return d
        d = d.replace("Credit sale", pdf_text.label("Credit sale", L.lang)).replace("Payment received", pdf_text.label("Payment received", L.lang))
        for m in ("Cash", "Bank", "Easypaisa", "JazzCash"):
            d = d.replace(f"({m})", pdf_text.label(m, L.lang))
        return d
    rows = [[f"{r['date']:%d %b %Y}", desc(r["desc"]), money(r["debit"]) if r["debit"] else "-",
             money(r["credit"]) if r["credit"] else "-", money(r["balance"])] for r in led]
    if rows:
        heads = [pdf_text.label(k, L.lang) if L.ur else v for k, v in
                 (("Date", "Date"), ("Description", "Description"), ("Credit given", "Credit given"), ("Payment", "Payment"), ("Balance", "Balance"))]
        t, st = make_table(heads, rows, [2, 3, 4], col_widths=[25 * mm, 65 * mm, 30 * mm, 30 * mm, 30 * mm], lang=L.lang)
        st.append(("ALIGN", (0, 0), (-1, 0), "RIGHT") if L.ur else ("ALIGN", (2, 0), (-1, 0), "RIGHT"))
        t.setStyle(TableStyle(st))
        story.append(t)
    else:
        story.append(Paragraph(escape(L.t("No transactions")) if L.ur else "No khata transactions recorded.", L.style("e", 10)))
    story.append(Spacer(1, 12))
    for key, val, bold in (("Total credit", customer.total_credit, False), ("Total payments", customer.total_payments, False),
                           ("Outstanding balance", customer.balance, True)):
        if L.ur:
            story.append(Paragraph(escape(L.line(key, money(val))), L.style("s", 12 if bold else 10, bold=bold)))
        else:
            story.append(Paragraph(f"<b>{escape(key)}:</b> {escape(money(val))}", L.style("s", 12 if bold else 10)))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
