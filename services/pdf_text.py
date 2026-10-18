"""Urdu/Arabic text for PDFs: joins letters (reshaping), fixes right-to-left order and registers the bundled font."""
import re

import arabic_reshaper
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from bidi import get_display
except ImportError:  # older python-bidi releases
    from bidi.algorithm import get_display

from config import RESOURCE_DIR

FONT, FONT_BOLD = "NotoNaskh", "NotoNaskh-Bold"
_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_reshaper = arabic_reshaper.ArabicReshaper()
_registered = False


def register_fonts():
    global _registered
    if not _registered:
        d = RESOURCE_DIR / "static" / "fonts"
        pdfmetrics.registerFont(TTFont(FONT, str(d / "NotoNaskhArabic-Regular.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(d / "NotoNaskhArabic-Bold.ttf")))
        _registered = True


def shape(text):
    """Return text ready to draw with ReportLab. Text without Urdu/Arabic letters is returned unchanged."""
    text = "" if text is None else str(text)
    if not _ARABIC.search(text):
        return text
    return get_display(_reshaper.reshape(text), base_dir="R")


# ---- Urdu wording used on invoices / statements
UR = {
    "INVOICE": "انوائس", "Date": "تاریخ", "Bill to": "گاہک", "Walk-in customer": "عام گاہک", "Product": "آئٹم",
    "Qty": "مقدار", "Price": "قیمت", "Total": "کل", "Subtotal": "ذیلی میزان", "Discount": "رعایت", "Returns": "واپسی",
    "Grand total": "کل رقم", "Paid": "ادا شدہ", "Remaining": "باقی", "Payment method": "ادائیگی کا طریقہ",
    "VOIDED": "منسوخ شدہ", "returned": "واپس", "Phone": "فون",
    "Thank you": "خریداری کا شکریہ! دوبارہ تشریف لائیے۔",
    "STATEMENT": "کھاتہ اسٹیٹمنٹ", "Description": "تفصیل", "Credit given": "اُدھار دیا", "Payment": "ادائیگی",
    "Balance": "بیلنس", "Total credit": "کل اُدھار", "Total payments": "کل ادائیگیاں",
    "Outstanding balance": "واجب الادا رقم", "No transactions": "کوئی لین دین درج نہیں۔",
    "Credit sale": "اُدھار فروخت", "Payment received": "ادائیگی موصول",
    "Cash": "نقد", "Bank": "بینک", "Easypaisa": "ایزی پیسہ", "JazzCash": "جاز کیش", "Credit/Udhaar": "اُدھار",
}


def label(key, lang):
    return UR.get(key, key) if lang == "ur" else key
