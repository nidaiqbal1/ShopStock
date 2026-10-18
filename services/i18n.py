"""Small English -> Urdu label dictionary (navigation, dashboard, POS, receipts, common buttons).
Anything not listed simply stays in English."""
UR = {
    "Dashboard": "ڈیش بورڈ", "POS / New Sale": "نئی فروخت (POS)", "Sales": "فروخت", "Products": "مصنوعات",
    "Inventory": "اسٹاک", "Customers": "گاہک", "Khata (Udhaar)": "کھاتہ (اُدھار)", "Suppliers": "سپلائرز",
    "Purchases": "خریداری", "Expenses": "اخراجات", "Reports": "رپورٹس", "AI Assistant": "اے آئی اسسٹنٹ",
    "Settings": "ترتیبات", "Backup & Restore": "بیک اپ اور بحالی", "Users": "صارفین", "Logout": "لاگ آؤٹ",
    "Account": "اکاؤنٹ", "Search products, customers, suppliers...": "مصنوعات، گاہک، سپلائرز تلاش کریں...",
    "New Sale": "نئی فروخت", "Total products": "کل مصنوعات", "Total stock quantity": "کل اسٹاک مقدار",
    "Today's sales": "آج کی فروخت", "Today's profit": "آج کا منافع", "Total receivables": "کل وصولیاں",
    "Total expenses": "کل اخراجات", "Low-stock products": "کم اسٹاک مصنوعات", "Total customers": "کل گاہک",
    "Sales & profit (last 30 days)": "فروخت اور منافع (پچھلے 30 دن)", "Top-selling products": "سب سے زیادہ بکنے والی مصنوعات",
    "Expenses by category": "اقسام کے لحاظ سے اخراجات", "Stock status": "اسٹاک کی صورتحال",
    "No data available yet.": "ابھی کوئی ڈیٹا دستیاب نہیں۔", "No business data available yet.": "ابھی کاروباری ڈیٹا دستیاب نہیں۔",
    "Point of Sale": "پوائنٹ آف سیل", "Cart": "ٹوکری", "Clear": "صاف کریں", "Item": "آئٹم", "Qty": "مقدار", "Price": "قیمت",
    "Subtotal": "ذیلی میزان", "Discount": "رعایت", "Grand total": "کل رقم", "Payment method": "ادائیگی کا طریقہ",
    "Amount paid": "ادا شدہ رقم", "Customer": "گاہک", "Walk-in customer": "عام گاہک", "Remaining (udhaar)": "باقی رقم (اُدھار)",
    "Complete sale": "فروخت مکمل کریں", "Username": "صارف نام", "Password": "پاسورڈ", "Sign in": "لاگ ان",
    "Search": "تلاش", "Save": "محفوظ کریں", "Cancel": "منسوخ", "Add": "شامل کریں", "Delete": "حذف", "Edit": "ترمیم",
    "Invoice": "انوائس", "Date": "تاریخ", "Total": "کل", "Paid": "ادا شدہ", "Remaining": "باقی", "Thank you for shopping with us!": "خریداری کا شکریہ!",
    "AI Business Insights": "اے آئی کاروباری بصیرت", "Product": "مصنوعات", "Returns": "واپسی", "Bill to": "گاہک",
}


def translate(text, lang):
    return UR.get(text, text) if lang == "ur" else text
