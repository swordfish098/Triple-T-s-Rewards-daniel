# auth/routes.py
from urllib.parse import urlparse, urljoin

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import User, Role  # Role has DRIVER, SPONSOR, ADMINISTRATOR

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

def _is_safe_url(target):
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Already logged in → send them to their dashboard by role
        return _redirect_by_role(current_user)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(USERNAME=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")

            # respect ?next= if present and safe
            nxt = request.args.get("next")
            if nxt and _is_safe_url(nxt):
                return redirect(nxt)

            # otherwise send to role dashboard
            return _redirect_by_role(user)

        flash("Invalid username or password", "danger")

    return render_template("common/login.html")  # a shared login template

def _redirect_by_role(user):
    role = getattr(user, "USER_TYPE", None)
    if role == Role.ADMINISTRATOR:
        return redirect(url_for("administrator_bp.dashboard"))
    if role == Role.SPONSOR:
        return redirect(url_for("sponsor_bp.dashboard"))
    # default → driver
    return redirect(url_for("driver_bp.dashboard"))

@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
