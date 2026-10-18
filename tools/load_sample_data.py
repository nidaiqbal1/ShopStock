r"""OPTIONAL: fill ShopStock with realistic SAMPLE data so you can try every screen.

From the ShopStock folder run:
    python tools\load_sample_data.py
It refuses to run if the shop already has products (so it can't mix with your real data).
To remove the sample data later, stop the app and delete instance\\shopstock.db.
Do NOT use this on a customer's real shop.
Prices are rough PKR examples, not real market prices.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, datetime, timedelta

from app import create_app
from models.models import (Category, Customer, Expense, Payment, Product, Purchase, PurchaseItem,
                           Sale, SaleItem, Supplier, db, set_setting)
from services.inventory_service import change_stock

random.seed(42)
CREDIT = "Credit/Udhaar"

CATEGORIES = ["Grocery", "Beverages", "Dairy", "Household", "Personal Care", "Snacks"]
SUPPLIERS = [("Ali Traders", "Ali & Sons Wholesale", "0321 5551234", "Lahore, Akbari Mandi"),
             ("Bismillah Distributors", "Bismillah FMCG", "0300 7771122", "Lahore, Shahdara"),
             ("Rehman Dairy Agency", "Rehman Dairy", "0333 4445566", "Lahore, Ravi Road")]
# name, category, brand, unit, cost, price, min_stock, supplier idx, opening qty
PRODUCTS = [
    ("Basmati Rice 5kg", "Grocery", "Guard", "bag", 1650, 1850, 8, 0, 40),
    ("Atta (Flour) 10kg", "Grocery", "Sunridge", "bag", 1450, 1600, 10, 0, 50),
    ("Cooking Oil 5L", "Grocery", "Dalda", "bottle", 2650, 2850, 6, 0, 24),
    ("Sugar 1kg", "Grocery", "Local", "kg", 150, 170, 20, 0, 100),
    ("Tea Danedar 190g", "Grocery", "Tapal", "pack", 260, 295, 15, 1, 60),
    ("Lipton Yellow Label 95g", "Grocery", "Lipton", "pack", 235, 265, 15, 1, 50),
    ("Daal Chana 1kg", "Grocery", "Local", "kg", 260, 300, 10, 0, 40),
    ("Salt 800g", "Grocery", "National", "pack", 45, 60, 15, 0, 60),
    ("Pepsi 1.5L", "Beverages", "Pepsi", "bottle", 175, 200, 12, 1, 48),
    ("Coca-Cola 1.5L", "Beverages", "Coca-Cola", "bottle", 175, 200, 12, 1, 48),
    ("Mineral Water 1.5L", "Beverages", "Nestle", "bottle", 75, 100, 20, 1, 72),
    ("Milk Pack 1L", "Dairy", "Olpers", "pack", 270, 300, 12, 2, 36),
    ("Nestle Milkpak 1L", "Dairy", "Nestle", "pack", 265, 295, 12, 2, 36),
    ("Eggs (Dozen)", "Dairy", "Local", "dozen", 320, 380, 6, 2, 20),
    ("Butter 200g", "Dairy", "Blue Band", "pack", 330, 380, 5, 2, 15),
    ("Surf Excel 1kg", "Household", "Surf Excel", "pack", 640, 720, 8, 1, 24),
    ("Dish Wash Liquid 500ml", "Household", "Vim", "bottle", 210, 250, 6, 1, 18),
    ("Matchbox (10 pcs)", "Household", "Local", "pack", 40, 55, 10, 1, 40),
    ("Lux Soap", "Personal Care", "Lux", "pcs", 105, 125, 20, 1, 80),
    ("Lifebuoy Soap", "Personal Care", "Lifebuoy", "pcs", 95, 115, 20, 1, 80),
    ("Colgate Toothpaste 100g", "Personal Care", "Colgate", "pcs", 190, 225, 10, 1, 30),
    ("Sunsilk Shampoo 180ml", "Personal Care", "Sunsilk", "bottle", 320, 380, 6, 1, 18),
    ("Lays Chips Large", "Snacks", "Lays", "pack", 90, 110, 15, 1, 5),
    ("Nimko Mix 200g", "Snacks", "Local", "pack", 120, 160, 8, 0, 4),
    ("Biscuits Sooper", "Snacks", "EBM", "pack", 35, 50, 20, 1, 60),
]
CUSTOMERS = [("Ahmed Khan", "0300 1234567"), ("Fatima Bibi", "0312 2345678"), ("Muhammad Usman", "0321 3456789"),
             ("Ayesha Siddiqui", "0333 4567890"), ("Bilal Hussain", "0345 5678901"), ("Zainab Malik", "0301 6789012"),
             ("Imran Sheikh", "0322 7890123"), ("Saima Noor", "0314 8901234")]
EXPENSES = [("Shop rent", "Rent", 25000, 1), ("Electricity bill", "Electricity", 7800, 10), ("Internet bill", "Internet", 2500, 12),
            ("Helper salary", "Salaries", 22000, 1), ("Delivery transport", "Transport", 1800, 5), ("Shutter repair", "Maintenance", 3500, 18),
            ("Stationery & bags", "Miscellaneous", 1200, 8)]


def main():
    app = create_app()
    with app.app_context():
        if Product.query.count() or Customer.query.count() or Sale.query.count():
            sys.exit("This shop already has data. Sample data is only loaded into an empty shop.")
        today = date.today()
        set_setting("shop_name", "Sample General Store")
        set_setting("owner_name", "Shop Owner")
        set_setting("phone", "0300 0000000")
        set_setting("address", "Main Bazaar, Lahore")
        cats = {n: Category(name=n) for n in CATEGORIES}
        sups = [Supplier(name=n, company=c, phone=p, address=a) for n, c, p, a in SUPPLIERS]
        custs = [Customer(name=n, phone=p, address="Lahore") for n, p in CUSTOMERS]
        db.session.add_all(list(cats.values()) + sups + custs)
        db.session.flush()
        prods = []
        for i, (n, cat, brand, unit, cost, price, mn, si, qty) in enumerate(PRODUCTS, 1):
            p = Product(name=n, category=cats[cat], brand=brand, unit=unit, purchase_price=cost, selling_price=price,
                        min_stock=mn, supplier=sups[si], sku=f"SS{i:03d}", barcode=f"89690{i:05d}")
            db.session.add(p)
            prods.append((p, si, qty))
        db.session.flush()

        # opening purchases (30 days ago), one per supplier, mostly paid
        start = today - timedelta(days=30)
        for si, sup in enumerate(sups):
            pur = Purchase(supplier=sup, date=start, notes="Opening stock purchase")
            total = 0
            for p, psi, qty in prods:
                if psi == si:
                    pur.items.append(PurchaseItem(product=p, quantity=qty, unit_price=p.purchase_price, subtotal=qty * p.purchase_price))
                    total += qty * p.purchase_price
                    change_stock(p, qty, "in", "purchase", reference=f"Purchase from {sup.name}")
            pur.total = total
            pur.paid = total if si == 0 else round(total * 0.7)
            pur.payment_status = "Paid" if pur.paid >= total else "Partial"
            db.session.add(pur)

        # 30 days of sales
        counter = {}
        for off in range(30, -1, -1):
            d = today - timedelta(days=off)
            for _ in range(random.randint(3, 8)):
                chosen = random.sample([p for p, _, _ in prods], random.randint(1, 4))
                items, subtotal, cost = [], 0.0, 0.0
                for p in chosen:
                    qty = random.choice([1, 1, 1, 2, 2, 3])
                    if p.stock_qty - qty < (p.min_stock * 0.5 if p.name in ("Lays Chips Large", "Nimko Mix 200g") else 0):
                        continue
                    items.append((p, qty))
                if not items:
                    continue
                method = random.choices(["Cash", "Easypaisa", "JazzCash", "Bank", CREDIT], [50, 15, 10, 5, 20])[0]
                cust = random.choice(custs) if method == CREDIT or random.random() < 0.3 else None
                counter[d] = counter.get(d, 0) + 1
                sale = Sale(invoice_no=f"INV-{d:%Y%m%d}-{counter[d]:04d}", customer=cust, date=d, payment_method=method,
                            created_at=datetime.combine(d, datetime.min.time()) + timedelta(hours=random.randint(9, 20), minutes=random.randint(0, 59)))
                for p, qty in items:
                    sale.items.append(SaleItem(product=p, product_name=p.name, quantity=qty, purchase_price=p.purchase_price,
                                               selling_price=p.selling_price, subtotal=qty * p.selling_price,
                                               profit=qty * (p.selling_price - p.purchase_price)))
                    subtotal += qty * p.selling_price
                    cost += qty * p.purchase_price
                    change_stock(p, qty, "out", "sale", reference=sale.invoice_no)
                discount = random.choice([0, 0, 0, 20, 50]) if subtotal > 500 else 0
                total = subtotal - discount
                paid = 0.0 if method == CREDIT and random.random() < 0.6 else (round(total * random.choice([0.25, 0.5])) if method == CREDIT else total)
                sale.subtotal, sale.discount, sale.total = subtotal, discount, total
                sale.paid, sale.remaining, sale.profit = paid, round(total - paid, 2), round(total - cost, 2)
                db.session.add(sale)
        db.session.flush()

        # customers pay back part of their khata
        for c in custs:
            bal = c.balance
            if bal > 0 and random.random() < 0.7:
                amt = round(bal * random.choice([0.3, 0.5, 0.8]))
                if amt > 0:
                    db.session.add(Payment(customer=c, amount=amt, method=random.choice(["Cash", "Easypaisa"]),
                                           date=today - timedelta(days=random.randint(0, 6)), note="Sample payment"))
        db.session.add(Payment(supplier=sups[1], amount=5000, method="Bank", date=today - timedelta(days=10), note="Sample payment"))

        # this month's and last month's expenses
        for title, cat, amt, day in EXPENSES:
            for months_back in (0, 1):
                m = today.replace(day=1) - timedelta(days=1) if months_back else today
                d = date(m.year, m.month, min(day, 28))
                if d <= today:
                    db.session.add(Expense(title=title, category=cat, amount=round(amt * random.uniform(0.9, 1.1), -1), date=d))
        db.session.commit()
        print("Sample data loaded:")
        print(f"  {Product.query.count()} products, {Customer.query.count()} customers, {Supplier.query.count()} suppliers, "
              f"{Sale.query.count()} sales, {Expense.query.count()} expenses")
        print("  Start the app with: python app.py   (login: admin / admin123)")


if __name__ == "__main__":
    main()
