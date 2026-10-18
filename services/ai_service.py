"""Read-only AI business assistant (Google Gemini).

The model never sees the database directly. Each question is mapped to a few safe, read-only
functions below and ONLY their small result is sent along with the question. Passwords, hashes,
API keys and session data are never part of any result.
"""
import json
import os
import re
from datetime import date

import requests

from models.models import all_settings
from services import report_service as rs

SYSTEM_PROMPT = (
    "You are the business assistant inside ShopStock, a shop management app for a small retail shop in Pakistan. "
    "Answer ONLY from the JSON shop data supplied with the question. Never invent sales, customers, products, profit, "
    "stock, expenses or balances. If the data does not contain the answer, reply exactly: "
    "I don't have enough recorded data to answer that. "
    "You are read-only: you cannot change anything. Be concise, friendly and use the currency shown in the data."
)
NO_DATA = "I don't have enough recorded data to answer that."
ACTION_RE = re.compile(r"^\s*(?:please\s+|can you\s+|could you\s+|kindly\s+)?(?:delete|remove|erase|change|update|edit|modify|add|create|send|reset|clear|set)\b", re.I)


def is_configured():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return bool(key) and key != "your_api_key_here"


def _cur():
    return all_settings()["currency"]


# ------------------------------------------------------------ safe data functions
def get_today_sales():
    t = rs.sales_totals(date.today(), date.today())
    return {"date": str(date.today()), "currency": _cur(), "sales_total": t["total"], "gross_profit": t["profit"], "invoices": t["count"]}


def get_monthly_sales():
    today = date.today()
    t = rs.sales_totals(today.replace(day=1), today)
    return {"month": today.strftime("%B %Y"), "currency": _cur(), "sales_total": t["total"], "gross_profit": t["profit"], "invoices": t["count"]}


def get_total_profit():
    today = date.today()
    ms = today.replace(day=1)
    m, allt = rs.sales_totals(ms, today), rs.sales_totals(date(2000, 1, 1), today)
    exp_m = rs.expenses_total(ms, today)
    return {"currency": _cur(), "gross_profit_this_month": m["profit"], "expenses_this_month": exp_m,
            "net_profit_this_month": round(m["profit"] - exp_m, 2), "gross_profit_all_time": allt["profit"],
            "note": "gross profit = sales minus purchase cost of items sold, after discounts"}


def get_low_stock_products(limit=20):
    return {"low_stock_products": [{"name": p.name, "stock": p.stock_qty, "minimum": p.min_stock, "unit": p.unit}
                                   for p in rs.low_stock_products(limit)]}


def get_top_products(limit=5):
    today = date.today()
    return {"top_products_all_time": rs.top_products(limit=limit),
            "top_products_this_month": rs.top_products(today.replace(day=1), today, limit)}


def get_customer_balance(question=""):
    rec = rs.receivables()
    out = {"currency": _cur(), "total_receivable": round(sum(b for _, b in rec), 2),
           "customers_with_balance": [{"name": c.name, "outstanding": b} for c, b in rec[:10]]}
    from models.models import Customer
    for c in Customer.query.all():
        if c.name and c.name.lower() in question.lower():
            out["named_customer"] = {"name": c.name, "outstanding": c.balance}
    return out


def get_supplier_payables():
    pay = rs.payables()
    return {"currency": _cur(), "total_payable": round(sum(b for _, b in pay), 2),
            "suppliers": [{"name": s.name, "company": s.company, "payable": b} for s, b in pay[:10]]}


def get_expense_summary():
    today = date.today()
    ms = today.replace(day=1)
    return {"currency": _cur(), "total_all_time": rs.expenses_total(), "total_this_month": rs.expenses_total(ms, today),
            "by_category_this_month": rs.expense_by_category(ms, today)[:7],
            "by_category_all_time": rs.expense_by_category()[:7]}


def get_inventory_value():
    i = rs.inventory_summary()
    return {"currency": _cur(), "inventory_value_at_cost": i["value"], "inventory_value_at_selling_price": i["retail_value"],
            "products": i["products"], "total_units": i["total_qty"], "low_stock": i["low"], "out_of_stock": i["out"]}


def get_restock_suggestions():
    return {"restock_candidates": [
        {"name": p.name, "stock": p.stock_qty, "minimum": p.min_stock, "unit": p.unit,
         "suggested_order_qty_to_reach_double_minimum": max(round(p.min_stock * 2 - p.stock_qty, 2), 0)}
        for p in rs.low_stock_products(20)]}


def get_shop_summary():
    d = {}
    for f in (get_today_sales, get_monthly_sales, get_total_profit, get_inventory_value, get_expense_summary):
        d.update({f.__name__: f()})
    d["top"] = get_top_products(3)
    d["low_stock"] = get_low_stock_products(5)
    d["receivables"] = get_customer_balance()
    d["payables"] = get_supplier_payables()
    return d


INTENTS = [
    (r"summary|overview|how.*(business|shop)|everything", [get_shop_summary]),
    (r"suppl|payable|i owe|do i owe", [get_supplier_payables]),
    (r"owes? me|who owes|outstanding|receivable|udhaar|khata|balance|credit|owe", [get_customer_balance]),
    (r"today", [get_today_sales]),
    (r"month|monthly|sales", [get_monthly_sales]),
    (r"profit|earn|margin", [get_total_profit]),
    (r"sell|sold|top|best|most|popular", [get_top_products]),
    (r"restock|reorder|re-order|order", [get_restock_suggestions]),
    (r"low|stock|running out|out of", [get_low_stock_products]),
    (r"expense|spend|spent|cost|rent|bill", [get_expense_summary]),
    (r"inventory|worth|value", [get_inventory_value]),
]


def build_context(question):
    ctx, used = {}, []
    for pattern, funcs in INTENTS:
        if re.search(pattern, question, re.I):
            for f in funcs:
                if f.__name__ not in used:
                    used.append(f.__name__)
                    ctx[f.__name__] = f(question) if f is get_customer_balance else f()
    if not used:
        ctx["get_shop_summary"] = get_shop_summary()
        used.append("get_shop_summary")
    return ctx, used


def ask(question):
    q = (question or "").strip()[:500]
    if not q:
        return {"ok": False, "answer": "Please type a question."}
    if not is_configured():
        return {"ok": False, "configured": False, "answer": "AI Assistant is not configured."}
    if ACTION_RE.search(q):
        return {"ok": True, "answer": "I'm read-only: I can analyse and explain your shop data, but I can't delete, change or "
                                      "send anything. Please make that change yourself inside ShopStock. Nothing was changed."}
    ctx, used = build_context(q)
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"Shop data (JSON):\n{json.dumps(ctx, default=str)}\n\nQuestion: {q}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700}}
    try:
        r = requests.post(url, json=body, timeout=30,
                          headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"].strip(), "Content-Type": "application/json"})
        if r.status_code != 200:
            return {"ok": False, "answer": f"The AI service returned an error (HTTP {r.status_code}). Please check your API key and try again."}
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return {"ok": True, "answer": text or NO_DATA, "sources": used}
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return {"ok": False, "answer": "The AI service could not be reached right now. The rest of ShopStock works normally."}
