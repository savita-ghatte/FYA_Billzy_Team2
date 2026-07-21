from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import Product, Sale, ROLE_SUPER_ADMIN

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == ROLE_SUPER_ADMIN:
        return render_template("dashboard.html", super_admin=True)

    low_stock_items = Product.query.filter(
        Product.shop_id == current_user.shop_id,
        Product.archived.is_(False),
        Product.stock_qty <= Product.min_threshold,
    ).all()  # FR-3.3

    recent_sales = Sale.query.filter_by(shop_id=current_user.shop_id) \
        .order_by(Sale.timestamp.desc()).limit(5).all()

    total_products = Product.query.filter_by(shop_id=current_user.shop_id, archived=False).count()

    return render_template(
        "dashboard.html",
        super_admin=False,
        low_stock_items=low_stock_items,
        recent_sales=recent_sales,
        total_products=total_products,
    )
