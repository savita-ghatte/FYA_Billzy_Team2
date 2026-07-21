from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# Roles per SRS Section 2 (Access Control Matrix)
ROLE_SUPER_ADMIN = "super_admin"
ROLE_BUSINESSMAN = "businessman"
ROLE_STORE_MANAGER = "store_manager"
ROLE_BILLING_OPERATOR = "billing_operator"

ROLES = [ROLE_SUPER_ADMIN, ROLE_BUSINESSMAN, ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    is_active_flag = db.Column(db.Boolean, default=True)  # FR-1.3: activate/deactivate
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Store Managers / Billing Operators belong to a shop; Businessman owns shop(s)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # flask-login expects this property; we alias to our own active flag
    @property
    def is_active(self):
        return self.is_active_flag

    def can(self, module, action):
        """action: 'read' or 'write'. Enforces the Access Control Matrix (SRS 2)."""
        matrix = {
            ROLE_SUPER_ADMIN: {
                "system_settings": {"read", "write"},
                "staff": {"read", "write"},
                "profile_tax": {"read"},
                "inventory": {"read"},
            },
            ROLE_BUSINESSMAN: {
                "staff": {"read", "write"},
                "profile_tax": {"read", "write"},
                "inventory": {"read", "write"},
                "billing": {"read", "write"},
                "finance": {"read", "write"},
            },
            ROLE_STORE_MANAGER: {
                "staff": {"read"},
                "profile_tax": {"read"},
                "inventory": {"read", "write"},
                "billing": {"read", "write"},
                "finance": {"read"},
            },
            ROLE_BILLING_OPERATOR: {
                "inventory": {"read"},
                "billing": {"read", "write"},
            },
        }
        return action in matrix.get(self.role, {}).get(module, set())


class Shop(db.Model):
    __tablename__ = "shops"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    state = db.Column(db.String(80), nullable=False)  # FR-2.2 state tax localization
    gstin = db.Column(db.String(20))  # FR-2.3
    allow_backorders = db.Column(db.Boolean, default=False)  # Negative Stock Constraint
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    staff = db.relationship("User", foreign_keys=[User.shop_id], backref="shop")
    products = db.relationship("Product", backref="shop", lazy="dynamic")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(60))
    category = db.Column(db.String(80))
    cost_price = db.Column(db.Float, nullable=False, default=0)
    selling_price = db.Column(db.Float, nullable=False, default=0)
    tax_rate = db.Column(db.Float, nullable=False, default=0)  # percent
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    min_threshold = db.Column(db.Integer, nullable=False, default=5)  # FR-3.3
    batch_no = db.Column(db.String(60))  # FR-3.2
    expiry_date = db.Column(db.Date)  # FR-3.2
    archived = db.Column(db.Boolean, default=False)

    @property
    def low_stock(self):
        return self.stock_qty <= self.min_threshold


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # FR-5.1
    discount = db.Column(db.Float, default=0)
    subtotal = db.Column(db.Float, default=0)
    tax_total = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    payment_mode = db.Column(db.String(20))  # FR-4.3: Cash/Card/UPI/Wallet
    finalized = db.Column(db.Boolean, default=True)  # Tax Locking Rules

    shop = db.relationship("Shop")
    operator = db.relationship("User")
    items = db.relationship("SaleItem", backref="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(150))  # snapshot, in case product changes later
    qty = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)  # Tax Locking Rules: frozen price
    tax_rate_at_sale = db.Column(db.Float, nullable=False)  # frozen tax %

    product = db.relationship("Product")


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False)  # rent, electricity, supplier, etc.
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255))
    date = db.Column(db.Date, default=datetime.utcnow)

    shop = db.relationship("Shop")
