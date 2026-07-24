from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user

from extensions import db
from models import Sale, Expense
from decorators import permission_required

finance_bp = Blueprint("finance", __name__)


@finance_bp.route("/finance/sales")
@login_required
@permission_required("finance", "read")
def sales_ledger():
    """FR-5.1: itemized sales ledger."""
    sales = Sale.query.filter_by(shop_id=current_user.shop_id).order_by(Sale.timestamp.desc()).all()
    revenue = sum(s.total for s in sales)
    tax = sum(s.tax_total for s in sales)
    discount = sum(s.discount for s in sales)
    return render_template("finance/sales.html", sales=sales, revenue=revenue, tax=tax, discount=discount)


@finance_bp.route("/finance/expenses", methods=["GET", "POST"])
@login_required
@permission_required("finance", "write")
def expenses():
    """FR-5.2: operational expense tracking."""
    if request.method == "POST":
        expense = Expense(
            shop_id=current_user.shop_id,
            category=request.form["category"].strip(),
            amount=float(request.form["amount"]),
            note=request.form.get("note", "").strip(),
            date=datetime.strptime(request.form["date"], "%Y-%m-%d").date()
            if request.form.get("date") else datetime.utcnow().date(),
        )
        db.session.add(expense)
        db.session.commit()
        flash("Expense logged.", "success")
        return redirect(url_for("finance.expenses"))

    expense_list = Expense.query.filter_by(shop_id=current_user.shop_id).order_by(Expense.date.desc()).all()
    total_expense = sum(e.amount for e in expense_list)
    return render_template("finance/expenses.html", expenses=expense_list, total_expense=total_expense)


@finance_bp.route("/finance/tax-report")
@login_required
@permission_required("finance", "read")
def tax_report():
    """FR-5.3: downloadable tax summary (simplified as CSV export)."""
    sales = Sale.query.filter_by(shop_id=current_user.shop_id).order_by(Sale.timestamp).all()

    lines = ["Date,Sale ID,Subtotal,Tax,Discount,Total,Payment Mode"]
    for s in sales:
        lines.append(
            f"{s.timestamp:%Y-%m-%d},{s.id},{s.subtotal:.2f},{s.tax_total:.2f},"
            f"{s.discount:.2f},{s.total:.2f},{s.payment_mode}"
        )
    csv_data = "\n".join(lines)

    return Response(
        csv_data, mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tax_report_shop_{current_user.shop_id}.csv"},
    )
