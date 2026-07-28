from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import (
    User,
    Shop,
    ROLE_BUSINESSMAN,
    ROLE_STORE_MANAGER,
    ROLE_BILLING_OPERATOR,
)
from decorators import roles_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
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

        user = User(
            name=name,
            email=email,
            phone=phone,
            role=ROLE_BUSINESSMAN,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        shop = Shop(
            name=shop_name,
            owner_id=user.id,
            state=state,
            gstin=gstin,
        )
        db.session.add(shop)
        db.session.flush()

        user.shop_id = shop.id
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Invalid credentials.", "danger")
            return render_template("login.html")

        if not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return render_template("login.html")

        if not user.is_active_flag:
            flash("Account is inactive. Contact the administrator.", "danger")
            return render_template("login.html")

        # Login and set session lifetime
        login_user(user)
        session.permanent = True

        from flask import current_app
        current_app.permanent_session_lifetime = timedelta(minutes=30)

        flash(f"Welcome back, {user.name}!", "success")

        # Respect next parameter if present
        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)

        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email:
            flash("Please enter your email address.", "danger")
            return render_template("forgot_password.html")

        if not new_password or not confirm_password:
            flash("Please enter and confirm your new password.", "danger")
            return render_template("forgot_password.html")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("forgot_password.html")

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("forgot_password.html")

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No account found for that email address.", "danger")
            return render_template("forgot_password.html")

        user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("auth.profile"))

        existing_user = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_user:
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("auth.profile"))

        if new_password or confirm_password:
            if len(new_password) < 6:
                flash("Password must be at least 6 characters long.", "danger")
                return redirect(url_for("auth.profile"))
            if new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for("auth.profile"))
            current_user.set_password(new_password)

        current_user.name = name
        current_user.email = email
        current_user.phone = phone
        db.session.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    shop = Shop.query.get(current_user.shop_id) if current_user.shop_id else None
    return render_template("profile.html", shop=shop)


@auth_bp.route("/staff", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_BUSINESSMAN)
def staff():
    allowed_roles = (ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role")

            if not name or not email or not password:
                flash("Name, email, and password are required.", "danger")
                return redirect(url_for("auth.staff"))

            if role not in allowed_roles:
                flash("Invalid staff role.", "danger")
                return redirect(url_for("auth.staff"))

            if User.query.filter_by(email=email).first():
                flash("Email already in use.", "danger")
                return redirect(url_for("auth.staff"))

            staff_user = User(
                name=name,
                email=email,
                role=role,
                shop_id=current_user.shop_id,
            )
            staff_user.set_password(password)

            db.session.add(staff_user)
            db.session.commit()

            flash(
                f"{role.replace('_', ' ').title()} account created successfully.",
                "success",
            )

        elif action == "toggle":
            staff_id = request.form.get("staff_id", type=int)
            staff_user = db.session.get(User, staff_id) if staff_id else None

            if not staff_user:
                flash("Staff member not found.", "danger")
            elif (
                staff_user.shop_id != current_user.shop_id
                or staff_user.role not in allowed_roles
            ):
                flash("You cannot update this staff member.", "danger")
            else:
                staff_user.is_active_flag = not staff_user.is_active_flag
                db.session.commit()
                flash("Staff status updated.", "success")

        else:
            flash("Invalid staff action.", "danger")

        return redirect(url_for("auth.staff"))

    staff_members = (
        User.query.filter(
            User.shop_id == current_user.shop_id,
            User.role.in_(allowed_roles),
        )
        .order_by(User.name)
        .all()
    )

    return render_template(
        "staff.html",
        staff=staff_members,
        ROLE_STORE_MANAGER=ROLE_STORE_MANAGER,
        ROLE_BILLING_OPERATOR=ROLE_BILLING_OPERATOR,
    )
