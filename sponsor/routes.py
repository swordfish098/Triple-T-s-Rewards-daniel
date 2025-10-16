# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-72ca7a46f1915a7f669f3692e9b77d23b248eaee/sponsor/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, DRIVER_POINTS
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import User, Role, StoreSettings, db, DriverApplication, Sponsor, Notification
from extensions import db
import secrets
import string

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

def driver_query_for_sponsor(sponsor_id):
    return db.session.query(User).filter(User.USER_TYPE == Role.DRIVER, User.SPONSOR_ID == sponsor_id).all()

def next_user_code():
    last_user = User.query.order_by(User.USER_CODE.desc()).first()
    return (last_user.USER_CODE + 1) if last_user else 1

def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

@sponsor_bp.route("/users/new", methods=["GET", "POST"])
@role_required(Role.SPONSOR, allow_admin=True)
def _next_user_code():
    last = User.query.order_by(User.USER_CODE.desc()).first()
    return (last.USER_CODE + 1) if last else 1

@sponsor_bp.route("/sponsor/users/new", methods=["GET", "POST"])
@role_required(Role.SPONSOR, allow_admin=True)
def create_sponsor_user():
    if request.method == "GET":
        return render_template("sponsor/create_user.html")

    # POST
    username = (request.form.get("username") or "").strip()

    if not username:
        flash("Username is required.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    # 1) Explicit duplicate check first
    if User.query.filter_by(USERNAME=username).first():
        flash("That username is already taken. Please pick another.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    # 2) Build the user with ALL required fields filled
    new_user = User(
        USER_CODE=_next_user_code(),
        USERNAME=username,
        USER_TYPE=Role.SPONSOR,
        FNAME="Sponsor",
        LNAME="User",
        EMAIL=f"{username}@example.com",   # or collect a real email in the form
        CREATED_AT=datetime.utcnow(),
        POINTS=0,
        IS_ACTIVE=1,
        FAILED_ATTEMPTS=0,
        LOCKOUT_TIME=None,
        RESET_TOKEN=None,
        RESET_TOKEN_CREATED_AT=None,
        IS_LOCKED_OUT=0,
    )

    # Set a temporary password the sponsor can share with the new user
    # (Or generate one elsewhere and display it.)
    temp_password = "P@ssw0rd123"  # replace with your generator
    new_user.set_password(temp_password)

    try:
        db.session.add(new_user)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        # Surface the REAL reason to your logs; keep message friendly to user
        print("IntegrityError creating sponsor user:", repr(e))
        flash("Could not create user (constraint error). Check required fields or username.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))
    except Exception as e:
        db.session.rollback()
        print("Error creating sponsor user:", repr(e))
        flash("Unexpected error creating user.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    log_audit_event("SPONSOR_CREATE_USER", f"by={current_user.USERNAME} new_user={username} role=sponsor")
    flash(f"Sponsor account created for '{username}'. Temporary password: {temp_password}", "success")
    return redirect(url_for("sponsor_bp.list_sponsor_users"))


@sponsor_bp.route("/users", methods=["GET"])
@role_required(Role.SPONSOR, allow_admin=True)
def list_sponsor_users():
    sponsors = User.query.filter_by(USER_TYPE=Role.SPONSOR).order_by(User.USERNAME.asc()).all()
    return render_template("sponsor/list_users.html", users=sponsors)


# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    return render_template('sponsor/dashboard.html')

# Update Store Settings
@sponsor_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.ebay_category_id = request.form.get('ebay_category_id')
        settings.point_ratio = int(request.form.get('point_ratio'))
        db.session.commit()
        flash("Store settings updated successfully!", "success")
        return redirect(url_for('sponsor_bp.update_settings'))

    return render_template("sponsor/settings.html", settings=settings)


@sponsor_bp.route('/points', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points_page():
    """Display all drivers for awarding or removing points."""
    drivers = User.query.filter_by(USER_TYPE=Role.DRIVER).all()
    return render_template('sponsor/points.html', drivers=drivers)


@sponsor_bp.route('/points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points(driver_id):
    """
    Allows sponsors to award or remove points from a driver.
    The form must include:
      - 'action' = 'award' or 'remove'
      - 'points' = integer value
      - optional 'reason' (for removals)
    """
    driver = User.query.get_or_404(driver_id)
    action = request.form.get('action')
    points = request.form.get('points', type=int)
    reason = request.form.get('reason', '').strip() or "No reason provided."

    # Validate
    if not action or action not in ("award", "remove") or points is None or points <= 0:
        flash("Invalid request. Please provide an action (award/remove) and valid point amount.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    if action == "award":
        driver.POINTS += points
        db.session.commit()

        log_audit_event(
            DRIVER_POINTS,
            f"Sponsor {current_user.USERNAME} awarded {points} points to {driver.USERNAME}."
        )

        if getattr(driver, "wants_point_notifications", False):
            Notification.create_notification(
                recipient_code=driver.USER_CODE,
                sender_code=current_user.USER_CODE,
                message=f"You have been awarded {points} points by {current_user.USERNAME}."
            )

        flash(f"✅ Successfully awarded {points} points to {driver.USERNAME}.", "success")

    elif action == "remove":
        driver.POINTS -= points
        db.session.commit()

        log_audit_event(
            DRIVER_POINTS,
            f"Sponsor {current_user.USERNAME} removed {points} points from {driver.USERNAME}. Reason: {reason}"
        )

        if getattr(driver, "wants_point_notifications", False):
            Notification.create_notification(
                recipient_code=driver.USER_CODE,
                sender_code=current_user.USER_CODE,
                message=f"{points} points were removed from your account by {current_user.USERNAME}. Reason: {reason}"
            )

        flash(f"⚠️ Removed {points} points from {driver.USERNAME}.", "info")

    return redirect(url_for('sponsor_bp.manage_points_page'))


# Add a New Driver
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')

        existing_user = User.query.filter(
            (User.USERNAME == username) | (User.EMAIL == email)
        ).first()
        if existing_user:
            flash(f"Username or email already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))
        
        # Find the highest existing USER_CODE and increment it
        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            # Starting code for the first user if the table is empty
            new_user_code = 1

        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            new_user_code = 1

        new_driver = User(
            USER_CODE=new_user_code, 
            USERNAME=username,
            EMAIL=email,
            USER_TYPE=Role.DRIVER,
            FNAME="New",
            LNAME="Driver",
            CREATED_AT=datetime.utcnow(),
            IS_ACTIVE=1,
            IS_LOCKED_OUT=0
        )
        new_pass = new_driver.set_password()

        db.session.add(new_driver)
        db.session.commit()

        flash(f"Driver '{username}' has been created! Temporary Password: {new_pass}", "success")
        return redirect(url_for('sponsor_bp.dashboard'))
        
    # Show the form to add a new driver
    return render_template('sponsor/add_user.html')

@sponsor_bp.route('/drivers', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def driver_management():
    drivers = User.query.filter_by(USER_TYPE=Role.DRIVER).all()
    return render_template('sponsor/drivers.html', drivers=drivers)

# Sponsor Application
@sponsor_bp.route("/applications")
@login_required
def review_driver_applications():
    apps = DriverApplication.query.filter_by(SPONSOR_ID=current_user.USER_CODE, STATUS="Pending").all()
    return render_template("sponsor/review_driver_applications.html", applications=apps)

@sponsor_bp.route("/applications/<int:app_id>/<decision>")
@login_required
def driver_decision(app_id, decision):
    app = DriverApplication.query.get_or_404(app_id)
    if decision == "accept":
        app.STATUS = "Accepted"
    else:
        app.STATUS = "Rejected"
    db.session.commit()
    flash(f"Driver application {decision}ed!", "info")
    return redirect(url_for("sponsor_bp.review_driver_applications"))