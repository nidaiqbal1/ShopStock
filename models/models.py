"""Database models for ShopStock (SQLite via Flask-SQLAlchemy)."""
from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, event, func
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


DEFAULT_SETTINGS = {
    "shop_name": "My Shop",
    "owner_name": "",
    "phone": "",
    "address": "",
    "email": "",
    "currency": "Rs.",
    "low_stock_default": "5",
    "backup_folder": "",
    "invoice_lang": "en",
}


def now():
    return datetime.now()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), default="Administrator")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role = db.Column(db.String(10), default="owner", nullable=False)  # 'owner' or 'cashier'
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    @property
    def is_owner(self):
        return self.role == "owner"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    products = db.relationship("Product", back_populates="category")


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    products = db.relationship("Product", back_populates="supplier")
    purchases = db.relationship("Purchase", back_populates="supplier", order_by="Purchase.date.desc()")
    payments = db.relationship("Payment", back_populates="supplier", order_by="Payment.date.desc()")

    @property
    def total_purchased(self):
        return round(db.session.query(func.coalesce(func.sum(Purchase.total), 0))
                     .filter(Purchase.supplier_id == self.id).scalar(), 2)

    @property
    def total_paid(self):
        at_purchase = db.session.query(func.coalesce(func.sum(Purchase.paid), 0)) \
            .filter(Purchase.supplier_id == self.id).scalar()
        later = db.session.query(func.coalesce(func.sum(Payment.amount), 0)) \
            .filter(Payment.supplier_id == self.id).scalar()
        return round(at_purchase + later, 2)

    @property
    def payable(self):
        return round(self.total_purchased - self.total_paid, 2)


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_qty >= 0", name="ck_product_stock_nonneg"),
        CheckConstraint("purchase_price >= 0 AND selling_price >= 0", name="ck_product_price_nonneg"),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    sku = db.Column(db.String(60), unique=True)
    barcode = db.Column(db.String(60), unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    brand = db.Column(db.String(80))
    purchase_price = db.Column(db.Float, nullable=False, default=0)
    selling_price = db.Column(db.Float, nullable=False, default=0)
    stock_qty = db.Column(db.Float, nullable=False, default=0)
    min_stock = db.Column(db.Float, nullable=False, default=5)
    unit = db.Column(db.String(20), default="pcs")
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    category = db.relationship("Category", back_populates="products")
    supplier = db.relationship("Supplier", back_populates="products")
    movements = db.relationship("InventoryMovement", back_populates="product",
                                cascade="all, delete-orphan", order_by="InventoryMovement.id.desc()")

    @property
    def is_low(self):
        return self.stock_qty <= self.min_stock

    @property
    def status(self):
        if self.stock_qty <= 0:
            return "Out of Stock"
        return "Low Stock" if self.is_low else "In Stock"

    @property
    def stock_value(self):
        return round(self.stock_qty * self.purchase_price, 2)


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    sales = db.relationship("Sale", back_populates="customer", order_by="Sale.id.desc()")
    payments = db.relationship("Payment", back_populates="customer", order_by="Payment.id.desc()")

    @property
    def total_credit(self):
        """Unpaid amount left on all of this customer's sales."""
        return round(db.session.query(func.coalesce(func.sum(Sale.remaining), 0))
                     .filter(Sale.customer_id == self.id, Sale.status == "completed").scalar(), 2)

    @property
    def total_payments(self):
        return round(db.session.query(func.coalesce(func.sum(Payment.amount), 0))
                     .filter(Payment.customer_id == self.id).scalar(), 2)

    @property
    def balance(self):
        return round(self.total_credit - self.total_payments, 2)


class Sale(db.Model):
    __tablename__ = "sales"
    __table_args__ = (CheckConstraint("total >= 0 AND paid >= 0 AND remaining >= 0", name="ck_sale_amounts"),)
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(30), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    subtotal = db.Column(db.Float, nullable=False, default=0)
    discount = db.Column(db.Float, nullable=False, default=0)
    total = db.Column(db.Float, nullable=False, default=0)
    paid = db.Column(db.Float, nullable=False, default=0)
    remaining = db.Column(db.Float, nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=False)
    profit = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(10), nullable=False, default="completed")  # 'completed' / 'voided'
    returned_total = db.Column(db.Float, nullable=False, default=0)
    void_reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    customer = db.relationship("Customer", back_populates="sales")
    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    returns = db.relationship("SaleReturn", back_populates="sale", order_by="SaleReturn.id.desc()",
                              cascade="all, delete-orphan")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))  # NULL once the product is deleted
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)
    returned_qty = db.Column(db.Float, nullable=False, default=0)
    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")

    @property
    def returnable_qty(self):
        return round(self.quantity - self.returned_qty, 3)


class SaleReturn(db.Model):
    """Customer returned some items of a sale (refund / credit note)."""
    __tablename__ = "sale_returns"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    refund_amount = db.Column(db.Float, nullable=False)
    credit_applied = db.Column(db.Float, nullable=False, default=0)  # reduced the customer's khata
    cash_refunded = db.Column(db.Float, nullable=False, default=0)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    sale = db.relationship("Sale", back_populates="returns")
    items = db.relationship("SaleReturnItem", back_populates="sale_return", cascade="all, delete-orphan")


class SaleReturnItem(db.Model):
    __tablename__ = "sale_return_items"
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey("sale_returns.id"), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey("sale_items.id"), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    sale_return = db.relationship("SaleReturn", back_populates="items")
    sale_item = db.relationship("SaleItem")


class Purchase(db.Model):
    __tablename__ = "purchases"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    total = db.Column(db.Float, nullable=False, default=0)
    paid = db.Column(db.Float, nullable=False, default=0)
    payment_status = db.Column(db.String(10), nullable=False, default="Unpaid")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    supplier = db.relationship("Supplier", back_populates="purchases")
    items = db.relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))  # NULL once the product is deleted
    product_name = db.Column(db.String(150))
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")

    @property
    def display_name(self):
        return self.product.name if self.product else (self.product_name or "(deleted product)")


class Payment(db.Model):
    """A payment received from a customer (khata) or made to a supplier."""
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount"),
        CheckConstraint("(customer_id IS NULL) + (supplier_id IS NULL) = 1", name="ck_payment_party"),
    )
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(30), nullable=False, default="Cash")
    note = db.Column(db.String(255))
    date = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    customer = db.relationship("Customer", back_populates="payments")
    supplier = db.relationship("Supplier", back_populates="payments")


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expense_amount"),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, nullable=False)


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    movement_type = db.Column(db.String(3), nullable=False)  # 'in' / 'out'
    quantity = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(60))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    product = db.relationship("Product", back_populates="movements")


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(255))


def get_setting(key, default=None):
    row = db.session.get(Setting, key)
    if row is not None and row.value is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key, default)


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row is None:
        db.session.add(Setting(key=key, value=value))
    else:
        row.value = value


def all_settings():
    data = dict(DEFAULT_SETTINGS)
    for row in Setting.query.all():
        if row.key in data and row.value is not None:
            data[row.key] = row.value
    return data
