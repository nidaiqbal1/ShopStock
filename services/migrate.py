"""Tiny schema upgrader so databases created by older ShopStock versions keep working."""
import re

from sqlalchemy import inspect, text

from models.models import db

ADDITIONS = {
    "users": [("role", "VARCHAR(10) NOT NULL DEFAULT 'owner'"), ("must_change_password", "BOOLEAN NOT NULL DEFAULT 0")],
    "sales": [("status", "VARCHAR(10) NOT NULL DEFAULT 'completed'"), ("returned_total", "FLOAT NOT NULL DEFAULT 0"),
              ("void_reason", "VARCHAR(255)")],
    "sale_items": [("returned_qty", "FLOAT NOT NULL DEFAULT 0")],
    "purchase_items": [("product_name", "VARCHAR(150)")],
}


def _make_product_id_nullable(table):
    """Older databases had product_id NOT NULL; deleting a product with history needs it nullable.
    SQLite cannot alter a column, so rebuild the table (official 12-step recipe)."""
    with db.engine.connect() as c:
        info = c.execute(text(f"PRAGMA table_info({table})")).fetchall()
        col = next((r for r in info if r[1] == "product_id"), None)
        if col is None or not col[3]:  # already nullable
            return
        ddl = c.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).scalar()
        new_ddl = re.sub(r"(product_id\s+INTEGER)\s+NOT NULL", r"\1", ddl, count=1)
        new_ddl = new_ddl.replace(f"CREATE TABLE {table}", f"CREATE TABLE {table}__new", 1)
        new_ddl = new_ddl.replace(f'CREATE TABLE "{table}"', f"CREATE TABLE {table}__new", 1)
        cols = ", ".join(r[1] for r in info)
    raw = db.engine.raw_connection()
    try:
        raw.isolation_level = None
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")
        cur.execute(f"DROP TABLE IF EXISTS {table}__new")
        cur.execute(new_ddl)
        cur.execute(f"INSERT INTO {table}__new ({cols}) SELECT {cols} FROM {table}")
        cur.execute(f"DROP TABLE {table}")
        cur.execute(f"ALTER TABLE {table}__new RENAME TO {table}")
        cur.execute("COMMIT")
        cur.execute("PRAGMA foreign_keys=ON")
    except Exception:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        raw.close()


def upgrade():
    db.create_all()  # creates any brand-new tables
    insp = inspect(db.engine)
    for table, cols in ADDITIONS.items():
        if not insp.has_table(table):
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols:
            if name not in have:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    # remember product names on purchase lines so history survives product deletion
    db.session.execute(text("UPDATE purchase_items SET product_name = "
                            "(SELECT name FROM products WHERE products.id = purchase_items.product_id) "
                            "WHERE product_name IS NULL"))
    db.session.commit()
    db.session.close()
    for table in ("sale_items", "purchase_items"):
        if insp.has_table(table):
            _make_product_id_nullable(table)
