from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from models.models import (Category, InventoryMovement, Product, PurchaseItem, SaleItem, Supplier, db, get_setting)
from routes.auth import login_required, owner_required
from services.inventory_service import change_stock
from utils import clean, parse_float

bp = Blueprint("products", __name__)

SORTS = {"name": Product.name, "stock": Product.stock_qty, "price": Product.selling_price, "newest": Product.created_at}


def _search_filter(query, q):
    like = f"%{q}%"
    return query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like), Product.brand.ilike(like)))


@bp.route("/products")
@login_required
def list_products():
    q = clean(request.args.get("q"), 80)
    cat = request.args.get("category", type=int)
    low = request.args.get("low")
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")
    query = Product.query
    if q:
        query = _search_filter(query, q)
    if cat:
        query = query.filter(Product.category_id == cat)
    if low:
        query = query.filter(Product.stock_qty <= Product.min_stock)
    col = SORTS.get(sort, Product.name)
    query = query.order_by(col.desc() if order == "desc" else col.asc())
    return render_template("products.html", products=query.limit(500).all(), q=q, cat=cat, low=low, sort=sort, order=order,
                           categories=Category.query.order_by(Category.name).all())


def _apply(p, f, creating):
    name = clean(f.get("name"), 150)
    if not name:
        raise ValueError("Product name is required.")
    for field in ("sku", "barcode"):
        val = clean(f.get(field), 60) or None
        if val:
            dup = Product.query.filter(getattr(Product, field) == val)
            if p.id:
                dup = dup.filter(Product.id != p.id)
            if dup.first():
                raise ValueError(f"Another product already uses this {field.upper()}.")
        setattr(p, field, val)
    p.name = name
    p.brand = clean(f.get("brand"), 80) or None
    p.category_id = f.get("category_id", type=int) if db.session.get(Category, f.get("category_id", type=int) or 0) else None
    p.supplier_id = f.get("supplier_id", type=int) if db.session.get(Supplier, f.get("supplier_id", type=int) or 0) else None
    p.purchase_price = parse_float(f.get("purchase_price"), "Purchase price")
    p.selling_price = parse_float(f.get("selling_price"), "Selling price")
    default_min = float(get_setting("low_stock_default", "5") or 5)
    p.min_stock = parse_float(f.get("min_stock"), "Minimum stock", required=False) if f.get("min_stock", "").strip() else default_min
    p.unit = clean(f.get("unit"), 20) or "pcs"
    p.description = clean(f.get("description"), 1000) or None
    return parse_float(f.get("stock_qty"), "Stock quantity", required=False) if creating else 0


def _form_ctx(product=None):
    return dict(product=product, categories=Category.query.order_by(Category.name).all(),
                suppliers=Supplier.query.order_by(Supplier.name).all(), default_min=get_setting("low_stock_default", "5"))


@bp.route("/products/new", methods=["GET", "POST"])
@owner_required
def new_product():
    if request.method == "POST":
        try:
            p = Product()
            opening = _apply(p, request.form, True)
            db.session.add(p)
            db.session.flush()
            if opening > 0:
                change_stock(p, opening, "in", "opening stock", note="Opening stock when product was added")
            db.session.commit()
            flash(f"Product '{p.name}' added.", "success")
            return redirect(url_for("products.list_products"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
    return render_template("product_form.html", **_form_ctx())


@bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@owner_required
def edit_product(pid):
    p = db.get_or_404(Product, pid)
    if request.method == "POST":
        try:
            _apply(p, request.form, False)
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("products.view_product", pid=p.id))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
    return render_template("product_form.html", **_form_ctx(p))


@bp.route("/products/<int:pid>")
@login_required
def view_product(pid):
    p = db.get_or_404(Product, pid)
    return render_template("product_detail.html", p=p, movements=p.movements[:30])


@bp.route("/products/<int:pid>/delete", methods=["POST"])
@owner_required
def delete_product(pid):
    p = db.get_or_404(Product, pid)
    # keep sale/purchase history readable: lines keep the product name, only the link is removed
    SaleItem.query.filter_by(product_id=pid).update({"product_id": None})
    PurchaseItem.query.filter_by(product_id=pid).update({"product_id": None, "product_name": p.name})
    db.session.delete(p)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("products.list_products"))


@bp.route("/products/categories/add", methods=["POST"])
@owner_required
def add_category():
    name = clean(request.form.get("name"), 80)
    if not name:
        flash("Category name is required.", "error")
    elif Category.query.filter(db.func.lower(Category.name) == name.lower()).first():
        flash("That category already exists.", "error")
    else:
        db.session.add(Category(name=name))
        db.session.commit()
        flash(f"Category '{name}' added.", "success")
    return redirect(request.referrer or url_for("products.list_products"))


@bp.route("/products/categories/<int:cid>/delete", methods=["POST"])
@owner_required
def delete_category(cid):
    c = db.get_or_404(Category, cid)
    if c.products:
        flash("This category still has products. Move or delete them first.", "error")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("products.list_products"))


@bp.route("/products/api/search")
@login_required
def api_search():
    q = clean(request.args.get("q"), 80)
    query = Product.query
    if q:
        query = _search_filter(query, q)
    return jsonify([{"id": p.id, "name": p.name, "sku": p.sku, "barcode": p.barcode, "price": p.selling_price,
                     "stock": p.stock_qty, "unit": p.unit, "low": p.is_low} for p in query.order_by(Product.name).limit(30)])


# ------------------------------------------------------------------ inventory
@bp.route("/inventory")
@owner_required
def inventory():
    q = clean(request.args.get("q"), 80)
    query = Product.query
    if q:
        query = _search_filter(query, q)
    products = query.order_by(Product.name).all()
    moves = InventoryMovement.query.order_by(InventoryMovement.id.desc()).limit(30).all()
    return render_template("inventory.html", products=products, moves=moves, q=q,
                           total_value=round(sum(p.stock_value for p in products), 2))


@bp.route("/inventory/<int:pid>/move", methods=["POST"])
@owner_required
def move_stock(pid):
    p = db.get_or_404(Product, pid)
    kind = request.form.get("type")
    try:
        if kind not in ("in", "out"):
            raise ValueError("Invalid operation.")
        qty = parse_float(request.form.get("quantity"), "Quantity", minimum=0.001)
        reason = clean(request.form.get("reason"), 40) or ("manual stock in" if kind == "in" else "manual stock out")
        change_stock(p, qty, kind, reason, note=clean(request.form.get("note")))
        db.session.commit()
        flash(f"Stock {'added to' if kind == 'in' else 'removed from'} '{p.name}'. New stock: {p.stock_qty:g}", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("products.inventory"))
