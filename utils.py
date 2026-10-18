"""Small shared helpers: validation, formatting, phone normalisation."""
import math
import re

from flask import g


def clean(value, maxlen=255):
    return (value or "").strip()[:maxlen]


def parse_float(value, label, minimum=0.0, required=True, maximum=1_000_000_000):
    if isinstance(value, str):
        value = value.strip().replace(",", "")
    if value in (None, ""):
        if required:
            raise ValueError(f"{label} is required.")
        return 0.0
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.")
    if not math.isfinite(x):
        raise ValueError(f"{label} must be a valid number.")
    if x < minimum:
        raise ValueError(f"{label} must be at least {minimum:g}.")
    if x > maximum:
        raise ValueError(f"{label} is too large.")
    return round(x, 3)


def parse_date(value, label="Date", required=False):
    from datetime import date, datetime
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{label} is not a valid date.")


def currency():
    cur = getattr(g, "_currency", None)
    if cur is None:
        from models.models import get_setting
        cur = get_setting("currency", "Rs.")
        try:
            g._currency = cur
        except RuntimeError:
            pass
    return cur


def money(value):
    value = float(value or 0)
    body = f"{value:,.0f}" if abs(value - round(value)) < 0.005 else f"{value:,.2f}"
    return f"{currency()} {body}"


def fmt_qty(q):
    return f"{float(q or 0):g}"


def normalize_phone(phone):
    """Convert a Pakistani/International number into digits-only wa.me format (e.g. 923001234567)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "92" + digits[1:]
    elif len(digits) == 10 and digits.startswith("3"):
        digits = "92" + digits
    return digits if 10 <= len(digits) <= 15 else None
