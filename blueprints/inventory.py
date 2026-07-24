import sys
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import Product
from decorators import permission_required

inventory_bp = Blueprint("inventory", __name__)


def parse_product_form(form_data):
    """Safely extracts form data from HTML inputs and maps them to Product model attributes."""
    errors = []

    name = form_data.get("name", "").strip()
    if not name:
        errors.append("Product name is required.")

    # Numeric conversions with fallbacks
    try:
        cost_price = float(form_data.get("cost") or 0)
        selling_price = float(form_data.get("price") or 0)
        tax_rate = float(form_data.get("tax_rate") or 0)
    except ValueError:
        errors.append("Cost price, selling price, and tax rate must be valid numbers.")

    try:
        stock_qty = int(form_data.get("stock") or 0)
        min_threshold = int(form_data.get("min_stock") or 5)
    except ValueError:
        errors.append("Stock quantity and minimum stock must be whole numbers.")

    # Expiry Date parsing
    expiry_raw = form_data.get("expiry_date", "").strip()
    expiry_date = None
    if expiry_raw:
        try:
            expiry_date = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Expiry date must be in YYYY-MM-DD format.")

    # Dictionary mapping HTML inputs -> DB Model Attributes
    raw_data = {
        "name": name,
        "sku": form_data.get("sku", "").strip(),
        "category": form_data.get("category", "").strip(),
        "cost_price": cost_price if 'cost_price' in locals() else 0.0,
        "selling_price": selling_price if 'selling_price' in locals() else 0.0,
        "tax_rate": tax_rate if 'tax_rate' in locals() else 0.0,
        "stock_qty": stock_qty if 'stock_qty' in locals() else 0,
        "min_threshold": min_threshold if 'min_threshold' in locals() else 5,
        "batch_no": form_data.get("batch", "").strip(),
        "expiry_date": expiry_date,
        "description": form_data.get("description", "").strip(),
    }

    # Keep only attributes that actually exist on your Product model
    data = {}
    for key, value in raw_data.items():
        if hasattr(Product, key):
            data[key] = value

    return data, errors


@inventory_bp.route("/inventory")
@login_required
@permission_required("inventory", "read")
def list_products():
    """Renders the product inventory table list."""
    products = Product.query.filter_by(
        shop_id=current_user.shop_id, 
        archived=False
    ).all()
    
    # Calculate summary metrics safely
    categories_count = len(set(p.category for p in products if p.category))
    low_stock_count = sum(
        1 for p in products 
        if getattr(p, 'stock_qty', 0) <= getattr(p, 'min_threshold', 5) and getattr(p, 'stock_qty', 0) > 0
    )
    out_stock_count = sum(1 for p in products if getattr(p, 'stock_qty', 0) == 0)

    return render_template(
        "inventory/list.html", 
        products=products,
        categories=categories_count,
        low_stock=low_stock_count,
        out_stock=out_stock_count
    )


@inventory_bp.route("/inventory/new", methods=["GET", "POST"])
@login_required
@permission_required("inventory", "write")
def new_product():
    """Renders the form on GET, creates the product on POST."""
    if request.method == "POST":
        data, errors = parse_product_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("inventory/form.html", product=None)

        try:
            product = Product(
                shop_id=current_user.shop_id,
                **data
            )
            db.session.add(product)
            db.session.commit()
            flash("Product added successfully.", "success")
            return redirect(url_for("inventory.list_products"))
        except Exception as e:
            db.session.rollback()
            print(f"DATABASE ERROR ON CREATE: {e}", file=sys.stderr)
            flash("An error occurred while saving the product.", "danger")

    # CRITICAL: Ensures GET requests load form.html
    return render_template("inventory/form.html", product=None)


@inventory_bp.route("/inventory/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("inventory", "write")
def edit_product(product_id):
    """Renders the edit form on GET, updates product on POST."""
    product = Product.query.filter_by(
        id=product_id, 
        shop_id=current_user.shop_id
    ).first_or_404()

    if request.method == "POST":
        data, errors = parse_product_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("inventory/form.html", product=product)

        try:
            for key, value in data.items():
                if hasattr(product, key):
                    setattr(product, key, value)

            db.session.commit()
            flash("Product updated successfully.", "success")
            return redirect(url_for("inventory.list_products"))
        except Exception as e:
            db.session.rollback()
            print(f"DATABASE ERROR ON EDIT: {e}", file=sys.stderr)
            flash("An error occurred while updating the product.", "danger")

    return render_template("inventory/form.html", product=product)


@inventory_bp.route("/inventory/<int:product_id>/archive", methods=["POST"])
@login_required
@permission_required("inventory", "write")
def archive_product(product_id):
    """Soft deletes/archives a product."""
    product = Product.query.filter_by(
        id=product_id, 
        shop_id=current_user.shop_id
    ).first_or_404()

    try:
        product.archived = True
        db.session.commit()
        flash("Product archived.", "info")
    except Exception as e:
        db.session.rollback()
        print(f"DATABASE ERROR ON ARCHIVE: {e}", file=sys.stderr)
        flash("Could not archive product.", "danger")

    return redirect(url_for("inventory.list_products"))
