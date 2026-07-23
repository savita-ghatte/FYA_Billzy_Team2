from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user

from extensions import db
from models import Product, Sale, SaleItem
from decorators import permission_required

billing_bp = Blueprint("billing", __name__)

CART_KEY = "pos_cart"  # {product_id_str: qty}


def _get_cart():
    if CART_KEY not in session or not isinstance(session[CART_KEY], dict):
        session[CART_KEY] = {}
    return session[CART_KEY]


@billing_bp.route("/billing")
@login_required
@permission_required("billing", "read")
def pos():
    cart = _get_cart()
    products = Product.query.filter_by(shop_id=current_user.shop_id, archived=False).all()

    cart_lines = []
    subtotal = 0.0
    tax_total = 0.0

    if cart:
        # Optimization: Fetch all cart products in a single SQL query with tenant isolation
        product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
        products_by_id = {
            p.id: p 
            for p in Product.query.filter(
                Product.id.in_(product_ids), 
                Product.shop_id == current_user.shop_id
            ).all()
        }

        for pid_str, qty in list(cart.items()):
            product = products_by_id.get(int(pid_str))
            # Clean up cart if product no longer exists or doesn't belong to shop
            if not product:
                cart.pop(pid_str, None)
                session.modified = True
                continue

            line_subtotal = round(float(product.selling_price) * qty, 2)
            line_tax = round(line_subtotal * (float(product.tax_rate) / 100), 2)

            subtotal += line_subtotal
            tax_total += line_tax

            cart_lines.append({
                "product": product, 
                "qty": qty,
                "line_subtotal": line_subtotal, 
                "line_tax": line_tax,
            })

    subtotal = round(subtotal, 2)
    tax_total = round(tax_total, 2)
    total = round(subtotal + tax_total, 2)

    return render_template(
        "billing/pos.html", products=products, cart_lines=cart_lines,
        subtotal=subtotal, tax_total=tax_total, total=total,
    )


@billing_bp.route("/billing/cart/add", methods=["POST"])
@login_required
@permission_required("billing", "write")
def cart_add():
    cart = _get_cart()
    product_id_str = request.form.get("product_id")
    qty = int(request.form.get("qty", 1))

    if product_id_str:
        # Tenant boundary check: Ensure product belongs to current user's shop
        product = Product.query.filter_by(id=int(product_id_str), shop_id=current_user.shop_id).first()
        if product:
            new_qty = cart.get(product_id_str, 0) + qty
            if new_qty > 0:
                cart[product_id_str] = new_qty
            else:
                cart.pop(product_id_str, None)
            session.modified = True
        else:
            flash("Invalid product selected.", "danger")

    return redirect(url_for("billing.pos"))


@billing_bp.route("/billing/cart/remove", methods=["POST"])
@login_required
@permission_required("billing", "write")
def cart_remove():
    cart = _get_cart()
    product_id = request.form.get("product_id")
    if product_id in cart:
        cart.pop(product_id)
        session.modified = True

    return redirect(url_for("billing.pos"))


@billing_bp.route("/billing/checkout", methods=["POST"])
@login_required
@permission_required("billing", "write")
def checkout():
    """Checkout with row-level locks, shop verification, and tax locking."""
    cart = _get_cart()
    if not cart:
        flash("Cart is empty.", "warning")
        return redirect(url_for("billing.pos"))

    payment_mode = request.form.get("payment_mode", "Cash")
    
    try:
        discount = round(float(request.form.get("discount") or 0), 2)
    except ValueError:
        discount = 0.0

    shop = current_user.shop
    product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]

    try:
        # Lock products for update to prevent stock race conditions during concurrent checkouts
        products = Product.query.filter(
            Product.id.in_(product_ids),
            Product.shop_id == current_user.shop_id
        ).with_for_update().all()

        products_map = {p.id: p for p in products}
        
        line_items = []
        for pid_str, qty in cart.items():
            product = products_map.get(int(pid_str))
            if not product:
                flash("One or more items in your cart are invalid.", "danger")
                return redirect(url_for("billing.pos"))

            # Strict inventory constraint check under lock
            if qty > product.stock_qty and not shop.allow_backorders:
                flash(f"Insufficient stock for '{product.name}' (Available: {product.stock_qty}, Requested: {qty}).", "danger")
                db.session.rollback()
                return redirect(url_for("billing.pos"))

            line_items.append((product, qty))

        subtotal = round(sum(float(p.selling_price) * q for p, q in line_items), 2)
        tax_total = round(sum(float(p.selling_price) * q * (float(p.tax_rate) / 100) for p, q in line_items), 2)
        total = round(max(0.0, subtotal + tax_total - discount), 2)

        sale = Sale(
            shop_id=current_user.shop_id, 
            operator_id=current_user.id,
            discount=discount, 
            subtotal=subtotal, 
            tax_total=tax_total,
            total=total, 
            payment_mode=payment_mode, 
            finalized=True,
        )
        db.session.add(sale)
        db.session.flush()

        for product, qty in line_items:
            # Freeze transaction price & tax rate
            sale_item = SaleItem(
                sale_id=sale.id, 
                product_id=product.id, 
                product_name=product.name,
                qty=qty, 
                price_at_sale=product.selling_price, 
                tax_rate_at_sale=product.tax_rate,
            )
            db.session.add(sale_item)
            product.stock_qty -= qty

        db.session.commit()

        # Clear cart only after successful DB commit
        session[CART_KEY] = {}
        session.modified = True

        flash("Sale completed. Invoice generated.", "success")
        return redirect(url_for("billing.invoice", sale_id=sale.id))

    except Exception:
        db.session.rollback()
        flash("An error occurred during checkout. Please try again.", "danger")
        return redirect(url_for("billing.pos"))


@billing_bp.route("/billing/invoice/<int:sale_id>")
@login_required
@permission_required("billing", "read")
def invoice(sale_id):
    sale = Sale.query.filter_by(id=sale_id, shop_id=current_user.shop_id).first_or_404()
    return render_template("billing/invoice.html", sale=sale)
