"""WhatsApp click-to-chat links (no API needed)."""
from urllib.parse import quote

from utils import money, normalize_phone


def chat_link(phone, message=""):
    number = normalize_phone(phone)
    if not number:
        return None
    return f"https://wa.me/{number}" + (f"?text={quote(message)}" if message else "")


def invoice_message(sale, shop_name):
    name = sale.customer.name if sale.customer else "Customer"
    return (f"Assalam-o-Alaikum {name},\n\nThank you for shopping at {shop_name}.\n"
            f"Invoice: {sale.invoice_no}\nTotal: {money(sale.total)}\nPaid: {money(sale.paid)}\n"
            f"Remaining: {money(sale.remaining)}\n\nThank you.")


def reminder_message(customer, shop_name):
    return (f"Assalam-o-Alaikum {customer.name},\n\n"
            f"Your current outstanding balance with our shop is {money(customer.balance)}.\n\n"
            f"Please clear the pending amount when convenient.\n\nThank you.\n{shop_name}")
