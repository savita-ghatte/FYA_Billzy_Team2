from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import Product
from decorators import permission_required

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/inventory")
@login_required
@permission_required("inventory", "read")
def list_products():
    products = Product.query.filter_by(shop_id=current_user.shop_id, archived=False).all()
    return render_template("inventory/list.html", products=products)


@inventory_bp.route("/inventory/new", methods=["GET", "POST"])
@login_required
@permission_required("inventory", "write")
def new_product():
    if request.method == "POST":
        expiry = request.form.get("expiry_date")
        product = Product(
            shop_id=current_user.shop_id,
            name=request.form["name"].strip(),
            
            category=request.form.get("category", "").strip(),
            cost_price=float(request.form.get("cost_price") or 0),
            selling_price=float(request.form.get("selling_price") or 0),
            tax_rate=float(request.form.get("tax_rate") or 0),
            stock_qty=int(request.form.get("stock_qty") or 0),
            min_threshold=int(request.form.get("min_threshold") or 5),
            batch_no=request.form.get("batch_no", "").strip(),
            expiry_date=datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else None,
        )
        db.session.add(product)
        db.session.commit()
        flash("Product added.", "success")
        return redirect(url_for("inventory.list_products"))

    return render_template("inventory/form.html", product=None)


@inventory_bp.route("/inventory/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("inventory", "write")
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, shop_id=current_user.shop_id).first_or_404()

    if request.method == "POST":
        expiry = request.form.get("expiry_date")
        product.name = request.form["name"].strip()
        
        product.category = request.form.get("category", "").strip()
        product.cost_price = float(request.form.get("cost_price") or 0)
        product.selling_price = float(request.form.get("selling_price") or 0)
        product.tax_rate = float(request.form.get("tax_rate") or 0)
        product.stock_qty = int(request.form.get("stock_qty") or 0)
        product.min_threshold = int(request.form.get("min_threshold") or 5)
        product.batch_no = request.form.get("batch_no", "").strip()
        product.expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else None
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("inventory.list_products"))

    return render_template("inventory/form.html", product=product)


@inventory_bp.route("/inventory/<int:product_id>/archive", methods=["POST"])
@login_required
@permission_required("inventory", "write")
def archive_product(product_id):
    product = Product.query.filter_by(id=product_id, shop_id=current_user.shop_id).first_or_404()
    product.archived = True
    db.session.commit()
    flash("Product archived.", "info")
    return redirect(url_for("inventory.list_products"))
