from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import Product, Sale, User, ROLE_SUPER_ADMIN, ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == ROLE_SUPER_ADMIN:
        active_products = Product.query.filter_by(archived=False).count()
        low_stock = Product.query.filter(
            Product.archived.is_(False),
            Product.stock_qty <= Product.min_threshold
        ).count()
        recent_sales = Sale.query.order_by(Sale.timestamp.desc()).limit(5).all()
        staff_count = User.query.filter(
            User.role.in_([ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR])
        ).count()
        super_admin = True
    else:
        active_products = Product.query.filter_by(shop_id=current_user.shop_id, archived=False).count()
        low_stock = Product.query.filter(
            Product.shop_id == current_user.shop_id,
            Product.archived.is_(False),
            Product.stock_qty <= Product.min_threshold
        ).count()
        recent_sales = Sale.query.filter_by(shop_id=current_user.shop_id) \
            .order_by(Sale.timestamp.desc()).limit(5).all()
        staff_count = User.query.filter(
            User.shop_id == current_user.shop_id,
            User.role.in_([ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR])
        ).count()
        super_admin = False

    return render_template(
        "dashboard.html",
        super_admin=super_admin,
        active_products=active_products,
        low_stock=low_stock,
        recent_sales=recent_sales,
        staff_count=staff_count,
    )

