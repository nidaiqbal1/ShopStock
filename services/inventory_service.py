"""Stock changes. Every change goes through here so each one is recorded and stock never goes negative."""
from models.models import db, InventoryMovement
from utils import fmt_qty


def change_stock(product, quantity, movement_type, reason, reference=None, note=None):
    quantity = float(quantity)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if movement_type not in ("in", "out"):
        raise ValueError("Invalid stock movement.")
    new_qty = product.stock_qty + quantity if movement_type == "in" else product.stock_qty - quantity
    if new_qty < -1e-9:
        raise ValueError(f"Not enough stock for '{product.name}' (available: {fmt_qty(product.stock_qty)}).")
    product.stock_qty = round(max(new_qty, 0), 3)
    db.session.add(InventoryMovement(product=product, movement_type=movement_type, quantity=quantity,
                                     balance_after=product.stock_qty, reason=reason,
                                     reference=reference, note=(note or None)))
