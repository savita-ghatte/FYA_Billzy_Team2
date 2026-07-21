from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, Shop, ROLE_BUSINESSMAN, ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR
from decorators import roles_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """FR-1.1: Businessman self-registration (OTP step simplified/stubbed for MVP)."""
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form["password"]
        shop_name = request.form["shop_name"].strip()
        state = request.form["state"].strip()
        gstin = request.form.get("gstin", "").strip()

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("auth.register"))

        user = User(name=name, email=email, phone=phone, role=ROLE_BUSINESSMAN)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        shop = Shop(name=shop_name, owner_id=user.id, state=state, gstin=gstin)
        db.session.add(shop)
        db.session.flush()

        user.shop_id = shop.id
        db.session.commit()

        flash("Registration successful. Please log in. (OTP verification stubbed for demo)", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """FR-1.2: Login with encrypted credentials; session auto-expires after 30 min."""
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password) and user.is_active_flag:
            login_user(user)
            session.permanent = True
            from flask import current_app
            current_app.permanent_session_lifetime = timedelta(minutes=30)
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for("dashboard.index"))

        flash("Invalid credentials or inactive account.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/staff", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_BUSINESSMAN)
def staff():
    """FR-1.3: Businessman creates/updates/deactivates Store Managers & Billing Operators."""
    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            role = request.form["role"]

            if role not in (ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR):
                flash("Invalid role.", "danger")
                return redirect(url_for("auth.staff"))

            if User.query.filter_by(email=email).first():
                flash("Email already in use.", "danger")
                return redirect(url_for("auth.staff"))

            staff_user = User(
                name=name, email=email, role=role,
                shop_id=current_user.shop_id,
            )
            staff_user.set_password(password)
            db.session.add(staff_user)
            db.session.commit()
            flash(f"{role.replace('_', ' ').title()} account created.", "success")

        elif action == "toggle":
            staff_id = request.form["staff_id"]
            staff_user = User.query.get_or_404(staff_id)
            if staff_user.shop_id == current_user.shop_id:
                staff_user.is_active_flag = not staff_user.is_active_flag
                db.session.commit()
                flash("Staff status updated.", "success")

        return redirect(url_for("auth.staff"))

    staff_members = User.query.filter(
        User.shop_id == current_user.shop_id,
        User.role.in_([ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR]),
    ).all()
    return render_template("staff.html", staff_members=staff_members)
