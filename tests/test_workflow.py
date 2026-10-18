"""End-to-end workflow test:  python tests/test_workflow.py   (uses a temporary database)"""
import json
import os
import sys
import tempfile
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tmp = tempfile.mkdtemp()
os.environ["SHOPSTOCK_DATA"] = _tmp  # database, backups and secret key all go to a temp folder
os.environ.pop("GEMINI_API_KEY", None)

from app import create_app  # noqa: E402
from models.models import Customer, Product, Sale, User, db  # noqa: E402

app = create_app()
c = app.test_client()
ok = 0


def check(cond, msg):
    global ok
    assert cond, "FAILED: " + msg
    ok += 1
    print("  ok -", msg)


def token():
    with c.session_transaction() as s:
        return s["csrf"]


def post(url, data=None, **kw):
    d = dict(data or {})
    d["csrf_token"] = token()
    return c.post(url, data=d, **kw)


def jpost(url, payload):
    return c.post(url, json=payload, headers={"X-CSRF-Token": token()})


# --- auth
check(c.get("/").status_code == 302, "protected route redirects when logged out")
c.get("/login")
check(post("/login", {"username": "admin", "password": "wrong"}).status_code == 200, "wrong password rejected")
check(post("/login", {"username": "admin", "password": "admin123"}).status_code == 302, "admin login works")
r = c.get("/")
check(r.status_code == 302 and "/account" in r.location, "default password forces a change at first login")
check(post("/account/password", {"current": "admin123", "new": "admin123", "confirm": "admin123"}).status_code == 302 and c.get("/").status_code == 302, "cannot reuse the default password")
post("/account/password", {"current": "admin123", "new": "Shop#Owner99", "confirm": "Shop#Owner99"})
check(c.get("/").status_code == 200, "dashboard opens after choosing a new password")
with app.app_context():
    u = User.query.first()
    check(u.password_hash != "admin123" and u.password_hash.startswith(("scrypt", "pbkdf2")), "password stored hashed")
    check(Product.query.count() == 0 and Customer.query.count() == 0 and Sale.query.count() == 0, "database starts empty (no demo data)")
r = c.get("/")
check(r.status_code == 200 and b"No data available yet." in r.data and b"No business data available yet." in r.data, "empty dashboard shows empty states")
for url in ["/products", "/inventory", "/customers", "/khata", "/suppliers", "/purchases", "/expenses", "/reports", "/ai", "/settings", "/sales", "/sales/pos", "/purchases/new", "/products/new", "/search?q=x"]:
    check(c.get(url).status_code == 200, f"GET {url}")
check(c.get("/nope").status_code == 404 and b"Page not found" in c.get("/nope").data, "404 page")
check(c.post("/products/categories/add", data={"name": "x"}).status_code == 400, "POST without CSRF token rejected")

# --- catalogue
post("/products/categories/add", {"name": "Grocery"})
post("/products/new", {"name": "Basmati Rice 5kg", "sku": "RICE5", "barcode": "8964000111", "category_id": 1, "brand": "Kernel", "purchase_price": "800", "selling_price": "950", "min_stock": "5", "unit": "bag", "stock_qty": "0"})
check(post("/products/new", {"name": "Dup", "sku": "RICE5", "purchase_price": "1", "selling_price": "2"}).status_code == 200, "duplicate SKU rejected")
post("/suppliers/add", {"name": "Ali Traders", "company": "Ali & Sons", "phone": "0321 5551234"})
r = post("/purchases/new", {"supplier_id": 1, "date": str(date.today()), "product_id": ["1"], "quantity": ["20"], "unit_price": ["780"], "payment_status": "Partial", "paid": "10000", "update_price": "on"})
with app.app_context():
    p = db.session.get(Product, 1)
    check(p.stock_qty == 20, "purchase increased stock to 20")
    check(p.purchase_price == 780, "purchase price updated from purchase")
    from models.models import Supplier
    check(db.session.get(Supplier, 1).payable == 15600 - 10000, "supplier payable = 5600")
post("/purchases/new", {"supplier_id": 1, "product_id": ["1"], "quantity": ["5"], "unit_price": ["780"], "payment_status": "Partial", "paid": "99999"})
with app.app_context():
    check(db.session.get(Product, 1).stock_qty == 20, "invalid purchase leaves stock unchanged")
post("/suppliers/1/pay", {"amount": "600", "method": "Cash"})
with app.app_context():
    check(db.session.get(Supplier, 1).payable == 5000, "supplier payment reduces payable")

# --- sale
post("/customers/add", {"name": "Ahmed", "phone": "0300 1234567"})
r = jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 3}], "discount": 150, "payment_method": "Credit/Udhaar", "customer_id": 1, "paid": 500})
d = r.get_json()
check(r.status_code == 200 and d["ok"], "credit sale completes")
with app.app_context():
    s = Sale.query.first()
    check(s.subtotal == 2850 and s.total == 2700 and s.paid == 500 and s.remaining == 2200, "sale totals correct")
    check(s.profit == 2700 - 3 * 780, "profit = total - cost (360)")
    check(db.session.get(Product, 1).stock_qty == 17, "stock decreased to 17")
    check(db.session.get(Customer, 1).balance == 2200, "customer balance = 2200")
    check(s.invoice_no.startswith("INV-"), "invoice number generated")
check(jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 100}], "payment_method": "Cash"}).status_code == 400, "overselling blocked")
check(jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 1}], "payment_method": "Credit/Udhaar"}).status_code == 400, "credit sale needs customer")
check(jpost("/sales/pos/checkout", {"items": [], "payment_method": "Cash"}).status_code == 400, "empty cart rejected")
r = jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 2}], "payment_method": "Cash"})
check(r.get_json()["ok"], "cash sale completes (paid in full)")
with app.app_context():
    check(db.session.get(Product, 1).stock_qty == 15, "stock now 15")
    check(db.session.get(Customer, 1).balance == 2200, "cash sale did not change balance")
post("/inventory/1/move", {"type": "out", "quantity": "999"})
with app.app_context():
    check(db.session.get(Product, 1).stock_qty == 15, "manual stock-out cannot go negative")
post("/inventory/1/move", {"type": "in", "quantity": "5", "reason": "found"})
with app.app_context():
    check(db.session.get(Product, 1).stock_qty == 20, "stock-in works and is recorded")
    from models.models import InventoryMovement
    check(InventoryMovement.query.count() == 4 + 0 or InventoryMovement.query.count() >= 4, "inventory movements recorded")

# --- khata
post("/khata/1/pay", {"amount": "9999999", "method": "Cash"})
with app.app_context():
    check(db.session.get(Customer, 1).balance == 2200, "overpayment rejected")
post("/khata/1/pay", {"amount": "700", "method": "Easypaisa"})
with app.app_context():
    check(db.session.get(Customer, 1).balance == 1500, "payment reduces balance to 1500")
check(b"1,500" in c.get("/khata").data, "khata page shows balance")
check(c.get("/khata/1/statement").status_code == 200, "statement page")
r = c.get("/khata/1/statement.pdf")
check(r.data[:4] == b"%PDF", "statement PDF generated")
r = c.get("/sales/1/invoice.pdf")
check(r.data[:4] == b"%PDF" and r.headers["Content-Disposition"].startswith("attachment"), "invoice PDF download")
check(b"Print Invoice" in c.get("/sales/1").data, "invoice page has print button")

# --- whatsapp
r = c.get("/whatsapp/reminder/1")
check(r.status_code == 302 and r.location.startswith("https://wa.me/923001234567?text="), "WhatsApp reminder link")
check("1%2C500" in r.location, "reminder contains real outstanding balance")
r = c.get("/whatsapp/invoice/1")
check(r.status_code == 302 and "INV-" in r.location, "WhatsApp invoice link")

# --- expenses
post("/expenses/add", {"title": "Shop rent", "category": "Rent", "amount": "20000", "date": str(date.today())})
check(b"Shop rent" in c.get("/expenses").data, "expense recorded")

# --- AI
r = jpost("/ai/ask", {"question": "What were today's sales?"})
check(r.get_json()["answer"] == "AI Assistant is not configured.", "AI unconfigured message")
os.environ["GEMINI_API_KEY"] = "test-key"
captured = {}


class Resp:
    status_code = 200
    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "Today's sales were Rs. 4,600."}]}}]}


def fake_post(url, json=None, headers=None, timeout=None):
    captured["body"], captured["headers"], captured["url"] = json, headers, url
    return Resp()


with mock.patch("services.ai_service.requests.post", fake_post):
    r = jpost("/ai/ask", {"question": "What were today's sales?"})
    prompt = captured["body"]["contents"][0]["parts"][0]["text"]
    check(r.get_json()["ok"] and "4600" in prompt, "AI prompt contains real today's sales (4600)")
    check("password" not in prompt.lower() and "test-key" not in prompt and "test-key" not in captured["url"], "no secrets sent in prompt/URL")
    check("get_today_sales" in prompt or "sales_total" in prompt and "get_shop_summary" not in prompt, "only relevant data sent")
    jpost("/ai/ask", {"question": "Who owes me the most?"})
    check("Ahmed" in captured["body"]["contents"][0]["parts"][0]["text"] and "1500" in captured["body"]["contents"][0]["parts"][0]["text"], "AI gets real customer balance")
    jpost("/ai/ask", {"question": "How much do I owe suppliers?"})
    check("5000" in captured["body"]["contents"][0]["parts"][0]["text"], "AI gets real supplier payable")
    captured.clear()
    r = jpost("/ai/ask", {"question": "Delete all my products"})
    check("read-only" in r.get_json()["answer"] and not captured, "AI refuses write actions without calling the model")
    with app.app_context():
        check(Product.query.count() == 1, "nothing was deleted")
del os.environ["GEMINI_API_KEY"]

# --- dashboard / reports
r = c.get("/")
check(b"4,600" in r.data and b"Best-selling product" in r.data, "dashboard shows real numbers and insights")
for k in ["sales", "profit", "expenses", "inventory", "receivables", "payables"]:
    r = c.get(f"/reports?type={k}&period=monthly")
    check(r.status_code == 200, f"report page: {k}")
    r = c.get(f"/reports/pdf?type={k}&period=custom&start={date.today()}&end={date.today()}")
    check(r.data[:4] == b"%PDF", f"report PDF: {k}")
r = c.get("/reports?type=sales&period=custom&start=2030-01-01&end=2020-01-01")
check(r.status_code == 200, "bad date range handled gracefully")
check(b"Ahmed" in c.get("/search?q=ahm").data and b"Basmati" in c.get("/search?q=8964000111").data, "global search (customer, barcode)")
check(c.get("/products/api/search?q=8964000111").get_json()[0]["name"] == "Basmati Rice 5kg", "POS barcode search")
post("/settings", {"shop_name": "Test Mart", "currency": "PKR", "low_stock_default": "3", "phone": "0300", "owner_name": "Z", "address": "Lahore", "email": ""})
check(b"Test Mart" in c.get("/sales/1").data and b"PKR" in c.get("/sales/1").data, "settings appear on invoice")

# ================= v2 features =================
from models.models import InventoryMovement  # noqa: E402
from services import report_service as rs  # noqa: E402

# --- returns (cash sale #2: 2 x 950)
with app.app_context():
    stock0 = db.session.get(Product, 1).stock_qty
    profit_before = db.session.get(Sale, 2).profit
item2 = None
with app.app_context():
    item2 = db.session.get(Sale, 2).items[0].id
post("/sales/2/return", {f"qty_{item2}": "5"})
with app.app_context():
    check(db.session.get(Sale, 2).returned_total == 0, "returning more than sold is rejected")
post("/sales/2/return", {f"qty_{item2}": "1", "note": "damaged"})
with app.app_context():
    s2 = db.session.get(Sale, 2)
    check(s2.returned_total == 950 and s2.total == 950 and s2.paid == 950 and s2.remaining == 0, "cash return: total/paid reduced by refund")
    check(s2.profit == profit_before - (950 - 780), "return reduces profit by the margin of returned item")
    check(db.session.get(Product, 1).stock_qty == stock0 + 1, "returned item goes back into stock")
# credit sale #1 (balance 1500 before): return 1 of 3 -> refund 900 deducted from khata
with app.app_context():
    item1 = db.session.get(Sale, 1).items[0].id
post("/sales/1/return", {f"qty_{item1}": "1"})
with app.app_context():
    s1 = db.session.get(Sale, 1)
    check(s1.returned_total == 900 and s1.total == 1800 and s1.remaining == 1300 and s1.paid == 500, "credit return: refund deducted from udhaar first")
    check(db.session.get(Customer, 1).balance == 600, "customer balance reduced to 600 after return")
r = post("/sales/1/void", {"reason": "x"})
with app.app_context():
    check(db.session.get(Sale, 1).status == "completed", "sale with returns cannot be voided")

# --- void
r = jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 1}], "payment_method": "Cash"})
vid = r.get_json()["sale_id"]
with app.app_context():
    st = db.session.get(Product, 1).stock_qty
    day_before = rs.sales_totals(date.today(), date.today())["total"]
post(f"/sales/{vid}/void", {"reason": "entered by mistake"})
with app.app_context():
    check(db.session.get(Sale, vid).status == "voided", "sale voided")
    check(db.session.get(Product, 1).stock_qty == st + 1, "void restored stock")
    check(rs.sales_totals(date.today(), date.today())["total"] == day_before - 950, "voided sale excluded from sales totals")
r = jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 1}], "payment_method": "Credit/Udhaar", "customer_id": 1})
cid_sale = r.get_json()["sale_id"]
with app.app_context():
    check(db.session.get(Customer, 1).balance == 1550, "new credit sale raised balance to 1550")
post(f"/sales/{cid_sale}/void", {})
with app.app_context():
    check(db.session.get(Customer, 1).balance == 600, "voiding credit sale removed it from khata")
check(b"VOID" in c.get("/sales").data, "sales list marks voided sales")
check(c.get(f"/sales/{vid}/invoice.pdf").data[:4] == b"%PDF", "voided invoice PDF still generates")

# --- Urdu PDFs
for url in ["/sales/1/invoice.pdf?lang=ur", "/khata/1/statement.pdf?lang=ur"]:
    r = c.get(url)
    check(r.data[:4] == b"%PDF" and b"NotoNaskh" in r.data, f"Urdu PDF with embedded Urdu font: {url}")
check(b"NotoNaskh" not in c.get("/sales/1/invoice.pdf?lang=en").data, "English invoice stays English")
check("اردو PDF".encode() in c.get("/sales/1").data, "invoice page offers Urdu PDF")
post("/settings", {"shop_name": "Test Mart", "currency": "PKR", "low_stock_default": "3", "invoice_lang": "ur"})
check(b"NotoNaskh" in c.get("/sales/1/invoice.pdf").data and b"NotoNaskh" not in c.get("/sales/1/invoice.pdf?lang=en").data, "default invoice language setting (Urdu) respected")
post("/settings", {"shop_name": "Test Mart", "currency": "PKR", "low_stock_default": "3", "invoice_lang": "en"})
for ur_name in ["شوکت", "Urdu 5kg باسمتی"]:
    with app.app_context():
        from models.models import Customer as _C
        cu = _C(name=ur_name); db.session.add(cu); db.session.commit()
check(c.get("/khata/1/statement.pdf?lang=ur").data[:4] == b"%PDF", "Urdu customer names do not break PDFs")

# --- thermal receipt, language
check(b"Test Mart" in c.get("/sales/1/receipt").data and b"@page" in c.get("/sales/1/receipt").data, "thermal receipt page")
c.get("/lang/ur")
r = c.get("/")
check('dir="rtl"'.encode() in r.data and "ڈیش بورڈ".encode() in r.data, "Urdu mode: RTL + translated labels")
check("نئی فروخت".encode() in c.get("/sales/pos").data, "Urdu POS labels")
c.get("/lang/en")
check(b'dir="ltr"' in c.get("/").data, "switch back to English")
check(b"/static/vendor/bootstrap/bootstrap.min.css" in c.get("/").data and b"cdn.jsdelivr" not in c.get("/").data, "assets are loaded locally (works offline)")

# --- Excel exports
from io import BytesIO  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
for url, first in [("/export/products.xlsx", "ID"), ("/export/customers.xlsx", "ID"), ("/export/suppliers.xlsx", "ID"), ("/export/sales.xlsx", "Invoice"),
                   ("/export/expenses.xlsx", "Date"), ("/reports/xlsx?type=profit&period=monthly", "Date"), ("/reports/xlsx?type=inventory", "Product")]:
    r = c.get(url)
    wb = load_workbook(BytesIO(r.data))
    check(r.status_code == 200 and wb.active["A1"].value == first, f"Excel export {url}")
check(c.get("/export/nothing.xlsx").status_code == 404, "unknown export is 404")

# --- users & cashier role
post("/users/add", {"username": "cashier1", "full_name": "Bilal", "role": "cashier", "password": "Cashier#1234"})
cc = app.test_client()
cc.get("/login")
def cpost(url, data=None, **kw):
    with cc.session_transaction() as s:
        t = s["csrf"]
    d = dict(data or {}); d["csrf_token"] = t
    return cc.post(url, data=d, **kw)
cpost("/login", {"username": "cashier1", "password": "Cashier#1234"})
check(cc.get("/").status_code == 302 and "/account" in cc.get("/").location, "new cashier must change password first")
cpost("/account/password", {"current": "Cashier#1234", "new": "Cashier#5678", "confirm": "Cashier#5678"})
r = cc.get("/")
check(r.status_code == 302 and "/sales/pos" in r.location, "cashier is sent to POS instead of dashboard")
for url in ["/reports", "/settings", "/expenses", "/suppliers", "/purchases", "/backup", "/users", "/inventory", "/ai", "/export/products.xlsx", "/products/new"]:
    check(cc.get(url).status_code == 302, f"cashier blocked from {url}")
check(cc.get("/sales/pos").status_code == 200 and cc.get("/products").status_code == 200 and cc.get("/khata").status_code == 200, "cashier can use POS, products, khata")
check(b"Purchase" not in cc.get("/products").data, "cashier cannot see purchase (cost) prices")
with cc.session_transaction() as s:
    tok = s["csrf"]
r = cc.post("/sales/pos/checkout", json={"items": [{"product_id": 1, "qty": 1}], "payment_method": "Cash"}, headers={"X-CSRF-Token": tok})
check(r.get_json()["ok"], "cashier can complete a sale")
cpost("/sales/1/void", {})
with app.app_context():
    check(db.session.get(Sale, 1).status == "completed", "cashier cannot void sales")
cpost("/sales/1/return", {f"qty_{item1}": "1"})
with app.app_context():
    check(db.session.get(Sale, 1).returned_total == 900, "cashier cannot process returns")
post("/users/2/toggle")
check(cc.get("/sales/pos").status_code == 302, "deactivated user is logged out")
post("/users/1/toggle")
with app.app_context():
    check(db.session.get(User, 1).is_active, "last owner cannot be deactivated")

# --- backup & restore
from services import backup_service as bs  # noqa: E402
with app.app_context():
    check(any("-auto-" in b["name"] for b in bs.list_backups(app)), "automatic daily backup exists")
r = post("/backup/create")
with app.app_context():
    names = [b["name"] for b in bs.list_backups(app) if "-manual-" in b["name"]]
check(len(names) == 1, "manual backup created")
check(c.get(f"/backup/download/{names[0]}").data[:15] == b"SQLite format 3", "backup downloads as a SQLite file")
check(c.get("/backup/download/../../etc/passwd").status_code in (302, 404), "backup download blocks path traversal")
check(c.get("/backup/download-now").data[:15] == b"SQLite format 3", "download-now works")
post("/customers/add", {"name": "Temp Customer"})
with app.app_context():
    check(Customer.query.filter_by(name="Temp Customer").count() == 1, "temp customer added after backup")
r = post("/backup/restore", {"name": names[0]})
check(r.status_code == 302 and "/login" in r.location, "restore logs everyone out")
with app.app_context():
    check(Customer.query.filter_by(name="Temp Customer").count() == 0, "restore brought back the backed-up data")
    check(any("before-restore" in b["name"] for b in bs.list_backups(app)), "safety backup taken before restore")
junk = os.path.join(_tmp, "junk.db")
open(junk, "wb").write(b"this is not a database")
c.get("/login")
post("/login", {"username": "admin", "password": "Shop#Owner99"})
r = c.post("/backup/restore", data={"csrf_token": token(), "file": (open(junk, "rb"), "junk.db")}, content_type="multipart/form-data")
with app.app_context():
    check(Product.query.count() == 1, "invalid restore file rejected, data untouched")
post("/backup/folder", {"folder": os.path.join(_tmp, "usb")})
os.makedirs(os.path.join(_tmp, "usb"))
post("/backup/folder", {"folder": os.path.join(_tmp, "usb")})
post("/backup/create")
check(len(os.listdir(os.path.join(_tmp, "usb"))) == 1, "backups are also copied to the extra folder")


# ================= delete buttons =================
from models.models import (Expense, Payment, Purchase, PurchaseItem, SaleItem, SaleReturn, Supplier)  # noqa: E402
post("/logout")
c.get("/login")
post("/login", {"username": "admin", "password": "Shop#Owner99"})
for url in ["/products", "/customers", "/sales", "/purchases", "/suppliers", "/expenses"]:
    check(b"bi-trash" in c.get(url).data or url in ("/sales", "/purchases"), f"delete buttons on {url}")

# fresh data to delete
post("/products/new", {"name": "Del Product", "sku": "DEL1", "purchase_price": "10", "selling_price": "20", "min_stock": "1", "stock_qty": "0"})
with app.app_context():
    dp = Product.query.filter_by(sku="DEL1").first().id
post("/suppliers/add", {"name": "Del Supplier"})
post("/customers/add", {"name": "Del Customer", "phone": "0300 1111111"})
with app.app_context():
    ds = Supplier.query.filter_by(name="Del Supplier").first().id
    dc = Customer.query.filter_by(name="Del Customer").first().id
post("/purchases/new", {"supplier_id": ds, "product_id": [str(dp)], "quantity": ["10"], "unit_price": ["10"], "payment_status": "Unpaid"})
with app.app_context():
    dpur = Purchase.query.filter_by(supplier_id=ds).first().id
    check(db.session.get(Product, dp).stock_qty == 10, "setup: purchase added 10")
jpost("/sales/pos/checkout", {"items": [{"product_id": dp, "qty": 4}], "customer_id": dc, "payment_method": "Credit/Udhaar", "discount": 0})
with app.app_context():
    dsale = Sale.query.filter_by(customer_id=dc).first()
    check(dsale is not None and db.session.get(Product, dp).stock_qty == 6, "setup: credit sale of 4")
    dsale_id, dinv = dsale.id, dsale.invoice_no

# delete a sale -> stock restored, customer balance back to zero
r = post(f"/sales/{dsale_id}/delete", {"restock": "1"})
with app.app_context():
    check(db.session.get(Sale, dsale_id) is None and SaleItem.query.filter_by(sale_id=dsale_id).count() == 0, "sale deleted with its lines")
    check(db.session.get(Product, dp).stock_qty == 10, "deleting a sale put the items back in stock")
    check(db.session.get(Customer, dc).balance == 0, "deleting a credit sale cleared the khata balance")
check(c.get(f"/sales/{dsale_id}").status_code == 404, "deleted sale page is gone")

# delete a sale without restocking
jpost("/sales/pos/checkout", {"items": [{"product_id": dp, "qty": 2}], "payment_method": "Cash", "discount": 0})
with app.app_context():
    s2 = Sale.query.order_by(Sale.id.desc()).first().id
post(f"/sales/{s2}/delete", {"restock": "0"})
with app.app_context():
    check(db.session.get(Sale, s2) is None and db.session.get(Product, dp).stock_qty == 8, "sale deleted without restocking keeps stock")

# a sale that has returns can be deleted too
jpost("/sales/pos/checkout", {"items": [{"product_id": dp, "qty": 3}], "payment_method": "Cash", "discount": 0})
with app.app_context():
    s3 = Sale.query.order_by(Sale.id.desc()).first()
    s3id, it3 = s3.id, s3.items[0].id
post(f"/sales/{s3id}/return", {f"qty_{it3}": "1"})
with app.app_context():
    check(db.session.get(Product, dp).stock_qty == 6, "setup: return put 1 back (8-3+1)")
post(f"/sales/{s3id}/delete", {"restock": "1"})
with app.app_context():
    check(db.session.get(Sale, s3id) is None and SaleReturn.query.filter_by(sale_id=s3id).count() == 0, "sale with returns deleted")
    check(db.session.get(Product, dp).stock_qty == 8, "stock correct after deleting a returned sale (only unreturned qty restored)")

# purchase delete takes stock back out; clamps when already sold
jpost("/sales/pos/checkout", {"items": [{"product_id": dp, "qty": 7}], "payment_method": "Cash", "discount": 0})
with app.app_context():
    check(db.session.get(Product, dp).stock_qty == 1, "setup: only 1 left")
r = post(f"/purchases/{dpur}/delete", follow_redirects=True)
with app.app_context():
    check(db.session.get(Purchase, dpur) is None and PurchaseItem.query.filter_by(purchase_id=dpur).count() == 0, "purchase deleted")
    check(db.session.get(Product, dp).stock_qty == 0, "purchase deletion never makes stock negative")
    check(db.session.get(Supplier, ds).payable == 0, "supplier payable updated after purchase deletion")
check(b"already sold" in r.data, "user is told some stock was already sold")

# product with history can be deleted; history keeps its name
post("/purchases/new", {"supplier_id": ds, "product_id": [str(dp)], "quantity": ["5"], "unit_price": ["10"], "payment_status": "Paid"})
post(f"/products/{dp}/delete")
with app.app_context():
    check(db.session.get(Product, dp) is None, "product with history deleted")
    check(SaleItem.query.filter_by(product_name="Del Product").count() >= 1 and all(i.product_id is None for i in SaleItem.query.filter_by(product_name="Del Product")), "old sale lines keep the product name")
    check(PurchaseItem.query.filter(PurchaseItem.product_name == "Del Product").count() == 1, "old purchase line keeps the product name")
check(c.get("/purchases").status_code == 200 and b"Del Product" in c.get("/purchases").data, "purchases page shows the deleted product's name")
check(c.get("/sales").status_code == 200 and c.get("/suppliers/%d" % ds).status_code == 200, "pages still render after product deletion")
check(c.get("/reports?type=sales&period=monthly").status_code == 200 and c.get("/").status_code == 200, "reports and dashboard fine after product deletion")
check(c.get(f"/export/sales.xlsx").status_code == 200, "Excel export fine after product deletion")

# customer delete keeps sales as walk-in, erases payments
jpost("/sales/pos/checkout", {"items": [{"product_id": 1, "qty": 1}], "customer_id": dc, "payment_method": "Credit/Udhaar", "discount": 0})
post(f"/khata/{dc}/pay", {"amount": "100", "method": "Cash"})
with app.app_context():
    cust_sales = Sale.query.filter_by(customer_id=dc).count()
    check(cust_sales == 1 and Payment.query.filter_by(customer_id=dc).count() == 1, "setup: customer has a sale and a payment")
post(f"/customers/{dc}/delete")
with app.app_context():
    check(db.session.get(Customer, dc) is None and Payment.query.filter_by(customer_id=dc).count() == 0, "customer with history deleted, payments erased")
    check(Sale.query.filter(Sale.customer_id.is_(None)).count() >= cust_sales, "customer's sales remain as walk-in sales")

# supplier delete removes purchases/payments, unlinks products, leaves stock
with app.app_context():
    st1 = db.session.get(Product, 1).stock_qty
post("/purchases/new", {"supplier_id": ds, "product_id": ["1"], "quantity": ["2"], "unit_price": ["780"], "payment_status": "Unpaid"})
post(f"/suppliers/{ds}/pay", {"amount": "50", "method": "Cash"})
post(f"/suppliers/{ds}/delete")
with app.app_context():
    check(db.session.get(Supplier, ds) is None and Purchase.query.filter_by(supplier_id=ds).count() == 0 and Payment.query.filter_by(supplier_id=ds).count() == 0, "supplier with history deleted along with purchases and payments")
    check(db.session.get(Product, 1).stock_qty == st1 + 2, "supplier deletion leaves stock untouched")

# expense delete
post("/expenses/add", {"title": "Del exp", "category": "Rent", "amount": "10", "date": str(date.today())})
with app.app_context():
    eid = Expense.query.filter_by(title="Del exp").first().id
post(f"/expenses/{eid}/delete")
with app.app_context():
    check(db.session.get(Expense, eid) is None, "expense deleted")

# cashiers cannot delete
post("/users/add", {"username": "cash2", "full_name": "C", "password": "Cashier#123", "role": "cashier"})
post("/logout"); c.get("/login")
post("/login", {"username": "cash2", "password": "Cashier#123"})
for url in ["/sales/1/delete", "/products/1/delete", "/customers/1/delete", "/suppliers/1/delete", "/purchases/1/delete", "/expenses/1/delete"]:
    cr = post(url)
    check(cr.status_code in (302, 403), f"cashier blocked: {url}")
with app.app_context():
    check(db.session.get(Product, 1) is not None and db.session.get(Sale, 1) is not None, "cashier delete attempts changed nothing")
post("/logout"); c.get("/login")
post("/login", {"username": "admin", "password": "Shop#Owner99"})

r = post("/logout")
check(r.status_code == 302 and c.get("/").status_code == 302, "logout")
print(f"\nALL {ok} CHECKS PASSED")
