from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user

from extensions import db
from models import Product, Sale, SaleItem
from decorators import permission_required

billing_bp = Blueprint("billing", __name__)

CART_KEY = "pos_cart"  # {product_id: qty}, kept in session per operator


def _get_cart():
    return session.setdefault(CART_KEY, {})


@billing_bp.route("/billing")
@login_required
@permission_required("billing", "read")
def pos():
    cart = _get_cart()
    products = Product.query.filter_by(shop_id=current_user.shop_id, archived=False).all()

    cart_lines = []
    subtotal = 0.0
    tax_total = 0.0
    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        if not product:
            continue
        line_subtotal = product.selling_price * qty
        line_tax = line_subtotal * (product.tax_rate / 100)
        subtotal += line_subtotal
        tax_total += line_tax
        cart_lines.append({
            "product": product, "qty": qty,
            "line_subtotal": line_subtotal, "line_tax": line_tax,
        })

    return render_template(
        "billing/pos.html", products=products, cart_lines=cart_lines,
        subtotal=subtotal, tax_total=tax_total, total=subtotal + tax_total,
    )


@billing_bp.route("/billing/cart/add", methods=["POST"])
@login_required
@permission_required("billing", "write")
def cart_add():
    cart = _get_cart()
    product_id = request.form["product_id"]
    qty = int(request.form.get("qty", 1))
    new_qty = cart.get(product_id, 0) + qty
    if new_qty <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = new_qty
    session.modified = True
    return redirect(url_for("billing.pos"))


@billing_bp.route("/billing/cart/remove", methods=["POST"])
@login_required
@permission_required("billing", "write")
def cart_remove():
    cart = _get_cart()
    product_id = request.form["product_id"]
    cart.pop(product_id, None)
    session.modified = True
    return redirect(url_for("billing.pos"))


@billing_bp.route("/billing/cart/clear", methods=["POST"])
@login_required
@permission_required("billing", "write")
def cart_clear():
    session[CART_KEY] = {}
    session.modified = True
    flash("Cart cleared.", "info")
    return redirect(url_for("billing.pos"))



@billing_bp.route("/billing/checkout", methods=["POST"])
@login_required
@permission_required("billing", "write")
def checkout():
    """FR-4.1/4.2/4.3 plus Negative Stock Constraint and Tax Locking Rules."""
    cart = _get_cart()
    if not cart:
        flash("Cart is empty.", "warning")
        return redirect(url_for("billing.pos"))

    payment_mode = request.form.get("payment_mode", "Cash")
    discount = float(request.form.get("discount") or 0)

    # Validate stock before committing anything (Negative Stock Constraint)
    shop = current_user.shop
    line_items = []
    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        if not product:
            continue
        if qty > product.stock_qty and not shop.allow_backorders:
            flash(f"Insufficient stock for '{product.name}' (have {product.stock_qty}, need {qty}).", "danger")
            return redirect(url_for("billing.pos"))
        line_items.append((product, qty))

    subtotal = sum(p.selling_price * q for p, q in line_items)
    tax_total = sum(p.selling_price * q * (p.tax_rate / 100) for p, q in line_items)
    total = subtotal + tax_total - discount

    sale = Sale(
        shop_id=current_user.shop_id, operator_id=current_user.id,
        discount=discount, subtotal=subtotal, tax_total=tax_total,
        total=total, payment_mode=payment_mode, finalized=True,
    )
    db.session.add(sale)
    db.session.flush()

    for product, qty in line_items:
        # Tax Locking Rules: freeze price & tax rate at time of sale
        sale_item = SaleItem(
            sale_id=sale.id, product_id=product.id, product_name=product.name,
            qty=qty, price_at_sale=product.selling_price, tax_rate_at_sale=product.tax_rate,
        )
        db.session.add(sale_item)
        product.stock_qty -= qty  # allow negative only if backorders enabled

    db.session.commit()
    session[CART_KEY] = {}
    session.modified = True

    flash("Sale completed. Invoice generated.", "success")
    return redirect(url_for("billing.invoice", sale_id=sale.id))


@billing_bp.route("/billing/invoice/<int:sale_id>")
@login_required
@permission_required("billing", "read")
def invoice(sale_id):
    sale = Sale.query.filter_by(id=sale_id, shop_id=current_user.shop_id).first_or_404()
    return render_template("billing/invoice.html", sale=sale)
