# auth/routes.py
import base64
from io import BytesIO
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import pyotp
import qrcode
from models import User, Role  # Role has DRIVER, SPONSOR, ADMINISTRATOR
from datetime import datetime, timedelta
from extensions import db
from sqlalchemy import or_
from common.logging import log_audit_event, LOGIN_EVENT
# If auth_bp is defined in __init__.py and imported, use that.
# If defined here, the relative import might not be needed, but it's often harmless.
# Assuming auth_bp is defined here based on the original structure.

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

LOCKOUT_ATTEMPTS = 3
RESET_TOKEN_TTL_MINUTES = 30

# --- Helper Functions ---

def _is_safe_url(target: str) -> bool:
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc

def _redirect_by_role(user):
    """Redirects user based on their USER_TYPE after login."""
    role = getattr(user, "USER_TYPE", None)
    if role == Role.ADMINISTRATOR:
        return redirect(url_for("administrator_bp.dashboard"))
    if role == Role.SPONSOR:
        return redirect(url_for("sponsor_bp.dashboard"))
    # default → driver
    return redirect(url_for("driver_bp.dashboard"))

def dashboard_endpoint_redirect(user) -> str:
    """Helper to determine dashboard URL based on role (used for 2FA)."""
    mapping = {
        Role.ADMINISTRATOR: "administrator_bp.dashboard",
        Role.SPONSOR: "sponsor_bp.dashboard",
        Role.DRIVER: "driver_bp.dashboard",
    }
    return mapping.get(user.USER_TYPE, "common.index") # Fallback to common index if role unknown

# --- Routes ---

@auth_bp.route('/settings')
@login_required
def settings():
    """Renders the user settings page."""
    return render_template('auth/settings.html')

@auth_bp.route("/twofa/setup", methods=["GET"])
@login_required
def twofa_setup():
    """Handles the setup process for two-factor authentication."""
    if not current_user.TOTP_SECRET:
        current_user.TOTP_SECRET = pyotp.random_base32()
        db.session.commit()

    # Generate QR code URI
    uri = f"otpauth://totp/TripleTsRewards:{current_user.USERNAME}?secret={current_user.TOTP_SECRET}&issuer=TripleTsRewards"
    img = qrcode.make(uri)

    # Convert QR code image to data URL for embedding in HTML
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template("auth/setup_2fa.html", qr_data_url=qr_data_url, secret=current_user.TOTP_SECRET)

@auth_bp.route("/twofa/verify", methods=["POST"])
@login_required
def twofa_verify():
    """Verifies the TOTP token provided by the user during 2FA setup."""
    token = (request.form.get("token") or "").strip()
    if not current_user.TOTP_SECRET:
        flash("No 2FA setup in progress.", "warning")
        return redirect(url_for("auth.twofa_setup"))

    totp = pyotp.TOTP(current_user.TOTP_SECRET)
    if totp.verify(token, valid_window=1): # Allow a small time window drift
        current_user.TOTP_ENABLED = True
        db.session.commit()
        endpoint_redirect = dashboard_endpoint_redirect(current_user)
        flash("Two-factor authentication is enabled.", "success")
        return redirect(url_for(endpoint_redirect))
    else:
        flash("Invalid code. Please try again.", "danger")
        # Don't redirect immediately to setup, show the error on the verify page if possible,
        # or redirect back to setup page which should ideally show the form again.
        # This assumes setup_2fa.html can handle displaying the QR code again.
        return redirect(url_for("auth.twofa_setup"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(USERNAME=username).first()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        if not user:
            flash("Invalid username or password", "danger")
            log_audit_event(LOGIN_EVENT, f"FAIL user={username} ip={ip}")
            return render_template("common/login.html")

        if user.is_account_locked():
            lock_reason = user.LOCKED_REASON or "system"
            if lock_reason == "admin":
                until = user.LOCKOUT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC") if user.LOCKOUT_TIME else "indefinitely"
                flash(f"Your account has been locked by an administrator until {until}.", "danger")
            elif lock_reason == "failed_attempts":
                 until = user.LOCKOUT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC") if user.LOCKOUT_TIME else "later"
                 flash(f"Account locked due to too many failed login attempts. Try again {until}.", "danger")
            else: # Generic or unknown reason
                flash("Account locked. Please contact your administrator.", "danger")
            log_audit_event(LOGIN_EVENT, f"FAIL user={user.USERNAME} ip={ip} reason=locked({lock_reason})")
            return render_template("common/login.html")

        if not user.check_password(password):
            user.register_failed_attempt()
            db.session.commit()
            remaining = max(0, LOCKOUT_ATTEMPTS - user.FAILED_ATTEMPTS)
            flash(f"Invalid username or password. {remaining} attempts remaining before lockout.", "danger")
            log_audit_event(LOGIN_EVENT, f"FAIL user={user.USERNAME} ip={ip} attempts={user.FAILED_ATTEMPTS}")
            return render_template("common/login.html")

        # On successful password check
        user.clear_failed_attempts()
        db.session.commit()
        login_user(user) # Log the user in
        flash("Login successful!", "success")
        log_audit_event(LOGIN_EVENT, f"SUCCESS user={user.USERNAME} role={user.USER_TYPE} ip={ip}")

        # --- Redirect logic ---
        # If 2FA is enabled, redirect to verify step (implement this)
        # if user.TOTP_ENABLED:
        #    session['2fa_user_id'] = user.USER_CODE # Store user ID temporarily
        #    return redirect(url_for('auth.enter_2fa_code')) # Need a route/template for this

        next_page = request.args.get("next")
        if next_page and _is_safe_url(next_page):
            return redirect(next_page)
        return _redirect_by_role(user) # Redirect to role-specific dashboard

    # For GET request
    return render_template("common/login.html")


@auth_bp.get("/logout")
@login_required
def logout():
    """Handles user logout."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    uname = current_user.USERNAME
    urole = current_user.USER_TYPE

    log_audit_event("LOGOUT", f"user={uname} role={urole} ip={ip}") # Use a distinct event type

    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """Handles the request to reset a password (sends link/token)."""
    if request.method == "POST":
        identifier = request.form.get("username", "").strip() # Use username for lookup
        user = User.query.filter_by(USERNAME=identifier).first()

        if not user:
            # Avoid revealing if user exists - show generic message
            flash("If an account with that username exists, a password reset link has been sent (check console for now).", "info")
            log_audit_event("RESET REQUEST", f"Password reset requested for identifier '{identifier}' - User not found or lookup failed.")
            return render_template("common/reset_password.html") # Stay on the page

        token = user.generate_reset_token()
        db.session.commit()

        reset_url = url_for("auth.reset_token", token=token, _external=True)
        # !!! IMPORTANT: In a real app, EMAIL this link. Do NOT flash it. !!!
        print(f"Password reset link for {user.USERNAME}: {reset_url}") # For dev purposes
        flash(f"Password reset link generated (valid for {RESET_TOKEN_TTL_MINUTES} minutes). Check console.", "info") # Dev message
        log_audit_event("RESET REQUEST", f"Password reset link generated for user {user.USERNAME}.")
        # Redirect back to login or show a confirmation message page
        return redirect(url_for("auth.login"))

    # For GET request
    return render_template("common/reset_password.html")


@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_token(token: str):
    """Handles password reset using the provided token."""
    user = User.query.filter_by(RESET_TOKEN=token).first()

    # Check if token is valid and not expired
    if not user or not user.RESET_TOKEN_CREATED_AT:
        flash("Invalid or expired password reset token.", "danger")
        log_audit_event("RESET FAILED", f"Invalid token '{token}' used.")
        return redirect(url_for("auth.reset_password"))

    if datetime.utcnow() > user.RESET_TOKEN_CREATED_AT + timedelta(minutes=RESET_TOKEN_TTL_MINUTES):
        user.clear_reset_token()
        db.session.commit()
        flash("Password reset token has expired. Please request a new one.", "warning")
        log_audit_event("RESET EXPIRED", f"Password reset token expired for user {user.USERNAME}.")
        return redirect(url_for("auth.reset_password"))

    # Handle the password form submission
    if request.method == "POST":
        new_password = request.form.get("password","")
        confirm_password = request.form.get("confirm_password","")

        if not new_password or new_password != confirm_password:
            flash("Passwords do not match or are empty.", "danger")
            return render_template("common/reset_with_token.html", token=token) # Show form again

        # Add password complexity checks here if needed (length, characters, etc.)
        if len(new_password) < 8:
             flash("Password must be at least 8 characters long.", "danger")
             return render_template("common/reset_with_token.html", token=token)

        user.set_password(new_password)
        user.clear_reset_token()
        user.clear_failed_attempts() # Unlock account and clear attempts
        db.session.commit()

        flash("Your password has been reset successfully. You can now log in.", "success")
        log_audit_event("RESET SUCCESS", f"Password reset successful for user {user.USERNAME}.")
        return redirect(url_for("auth.login"))

    # For GET request (show the password reset form)
    return render_template("common/reset_with_token.html", token=token)