# triple-ts-rewards/.../sponsor/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, DRIVER_POINTS
from datetime import datetime
from sqlalchemy.exc import IntegrityError
# --- Use the combined imports from the 'main' branch ---
from models import User, Role, StoreSettings, db, DriverApplication, Sponsor, Notification, Driver, DriverSponsorAssociation, Purchase, AuditLog
# Removed redundant db import
import secrets
import string

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

# --- Helper Functions ---

def next_user_code():
    """Generates the next available USER_CODE."""
    last_user = User.query.order_by(User.USER_CODE.desc()).first()
    return (last_user.USER_CODE + 1) if last_user else 1

# Keep generate_temp_password
def generate_temp_password(length: int = 10) -> str:
    """Generates a random temporary password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

# --- Routes ---

# Dashboard (Keep as is)
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    return render_template('sponsor/dashboard.html')

# Update Store Settings (Keep sponsor-specific logic from 'main')
@sponsor_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    # Fetch or create settings specific to the current sponsor
    settings = StoreSettings.query.filter_by(sponsor_id=current_user.USER_CODE).first()
    if not settings:
        settings = StoreSettings(sponsor_id=current_user.USER_CODE)
        db.session.add(settings)

    if request.method == 'POST':
        settings.ebay_category_id = request.form.get('ebay_category_id', '2984') # Default if empty
        try:
            point_ratio_val = int(request.form.get('point_ratio', 10)) # Default if empty/invalid
            if point_ratio_val <= 0:
                flash("Point ratio must be a positive number.", "warning")
            else:
                settings.point_ratio = point_ratio_val
        except ValueError:
             flash("Invalid point ratio provided. Please enter a number.", "danger")
             return render_template("sponsor/settings.html", settings=settings)

        try:
            db.session.commit()
            flash("Store settings updated successfully!", "success")
            return redirect(url_for('sponsor_bp.update_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating settings: {e}", "danger")

    return render_template("sponsor/settings.html", settings=settings)

# Manage points page (Keep DriverSponsorAssociation logic from 'main')
@sponsor_bp.route('/points', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points_page():
    # Fetch associations specific to the current sponsor
    sort_by = request.args.get('sort_by')
    query = DriverSponsorAssociation.query.filter_by(sponsor_id=current_user.USER_CODE)

    # Apply sorting
    if sort_by == 'points_desc':
        query = query.order_by(DriverSponsorAssociation.points.desc())
    elif sort_by == 'points_asc':
        query = query.order_by(DriverSponsorAssociation.points.asc())
    else:
        query = query.order_by(DriverSponsorAssociation.driver_id.asc())

    associations = query.all()

    # Attach user info
    for assoc in associations:
        assoc.user = User.query.get(assoc.driver_id)

    return render_template('sponsor/points.html',
                           drivers=associations, # Pass associations
                           current_sort=sort_by)

# Manage points for a specific driver-sponsor relationship (Keep 'main' logic)
@sponsor_bp.route('/points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points(driver_id):
    association = DriverSponsorAssociation.query.get((driver_id, current_user.USER_CODE))
    if not association:
        flash("Driver is not associated with your organization.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    driver_user = User.query.get(driver_id)
    username = driver_user.USERNAME if driver_user else f"Driver ID {driver_id}"

    action = request.form.get('action')
    try:
        points = int(request.form.get('points', 0))
    except ValueError:
        flash("Invalid point amount entered.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    reason = request.form.get('reason', '').strip() or "No reason provided."

    if action not in ("award", "remove") or points <= 0:
        flash("Invalid action or point amount (must be positive).", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    log_message = ""
    notification_message = ""
    new_balance = association.points # Initialize with current balance

    if action == "award":
        association.points += points
        new_balance = association.points
        log_message = f"Sponsor {current_user.USERNAME} awarded {points} points to driver {username} (ID: {driver_id}). Reason: {reason}. New Balance: {new_balance}. Sponsor ID: {current_user.USER_CODE}."
        notification_message = f"🎉 **{current_user.FNAME} {current_user.LNAME}** awarded you {points} points! Balance: {new_balance}."
        flash(f"Awarded {points} points to {username}.", "success")
    elif action == "remove":
        if association.points < points:
             flash(f"Cannot remove {points} points. Driver {username} only has {association.points}.", "warning")
             return redirect(url_for('sponsor_bp.manage_points_page'))
        association.points -= points
        new_balance = association.points
        log_message = f"Sponsor {current_user.USERNAME} removed {points} points from driver {username} (ID: {driver_id}). Reason: {reason}. New Balance: {new_balance}. Sponsor ID: {current_user.USER_CODE}."
        notification_message = f"⚠️ **{current_user.FNAME} {current_user.LNAME}** removed {points} points. Reason: {reason}. Balance: {new_balance}."
        flash(f"Removed {points} points from {username}.", "info")

    log_entry = AuditLog(
        EVENT_TYPE=DRIVER_POINTS,
        DETAILS=log_message,
        CREATED_AT=datetime.utcnow()
    )
    db.session.add(log_entry)

    if driver_user and driver_user.wants_point_notifications:
        try:
            Notification.create_notification(
                recipient_code=driver_id,
                sender_code=current_user.USER_CODE,
                message=notification_message
            )
        except Exception as e:
            print(f"Error sending notification: {e}")
            flash("Points updated, but failed to send notification.", "warning")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating points: {e}", "danger")

    return redirect(url_for('sponsor_bp.manage_points_page'))

# Add a New Driver (Keep 'main' logic with automatic association)
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        license_number = request.form.get('license_number', '').strip() or None

        if not username or not email:
            flash("Username and Email are required.", "danger")
            return render_template('sponsor/add_user.html')

        if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
            flash("Username or email already exists.", "danger")
            return render_template('sponsor/add_user.html', username=username, email=email, license_number=license_number)

        new_user_code = next_user_code()
        new_user = User(
            USER_CODE=new_user_code, USERNAME=username, EMAIL=email,
            USER_TYPE=Role.DRIVER, FNAME="New", LNAME="Driver",
            CREATED_AT=datetime.utcnow(), IS_ACTIVE=1, IS_LOCKED_OUT=0
        )
        try:
            new_pass = new_user.admin_set_new_pass()
        except AttributeError:
             flash("Error: admin_set_new_pass method not found on User model.", "danger")
             return render_template('sponsor/add_user.html', username=username, email=email, license_number=license_number)

        db.session.add(new_user)
        new_driver_profile = Driver(
            DRIVER_ID=new_user_code,
            LICENSE_NUMBER=license_number if license_number else 'N/A'
        )
        db.session.add(new_driver_profile)
        association = DriverSponsorAssociation(
            driver_id=new_user_code, sponsor_id=current_user.USER_CODE, points=0
        )
        db.session.add(association)

        try:
            db.session.commit()
            flash(f"Driver '{username}' created and automatically associated. Temp Pass: {new_pass}", "success")
            return redirect(url_for('sponsor_bp.manage_points_page'))
        except IntegrityError as e:
             db.session.rollback()
             flash(f"Database error: Could not create driver. {e}", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template('sponsor/add_user.html')

# Driver application review (Keep 'main' logic)
@sponsor_bp.route("/applications")
@login_required
@role_required(Role.SPONSOR)
def review_driver_applications():
    apps = DriverApplication.query.filter_by(
        SPONSOR_ID=current_user.USER_CODE, STATUS="Pending"
    ).all()
    for app in apps:
        driver_user = User.query.get(app.DRIVER_ID)
        app.driver_name = driver_user.USERNAME if driver_user else f"ID: {app.DRIVER_ID}"
    return render_template("sponsor/review_driver_applications.html", applications=apps)

# Process driver application decision (Keep 'main' logic)
@sponsor_bp.route("/applications/<int:app_id>/<decision>", methods=['POST'])
@login_required
@role_required(Role.SPONSOR)
def driver_decision(app_id, decision):
    app = DriverApplication.query.get_or_404(app_id)
    if app.SPONSOR_ID != current_user.USER_CODE:
        flash("You are not authorized to process this application.", "danger")
        return redirect(url_for("sponsor_bp.review_driver_applications"))

    decision_lower = decision.lower()
    flash_msg = ""
    notify_msg = ""

    if decision_lower == "accept":
        app.STATUS = "Accepted"
        existing_assoc = DriverSponsorAssociation.query.get((app.DRIVER_ID, app.SPONSOR_ID))
        if not existing_assoc:
            association = DriverSponsorAssociation(
                driver_id=app.DRIVER_ID, sponsor_id=app.SPONSOR_ID, points=0
            )
            db.session.add(association)
            flash_msg = "Driver application accepted and association created!"
        else:
             flash_msg = "Driver application accepted (association already exists)."
        notify_msg = f"🎉 Your application to {current_user.FNAME} {current_user.LNAME}'s organization has been accepted!"

    elif decision_lower == "reject":
        app.STATUS = "Rejected"
        flash_msg = "Driver application rejected."
        notify_msg = f"ℹ️ Your application to {current_user.FNAME} {current_user.LNAME}'s organization has been rejected."
    else:
        flash("Invalid decision.", "warning")
        return redirect(url_for("sponsor_bp.review_driver_applications"))

    try:
        db.session.commit()
        flash(flash_msg, "info")
        # Send notification after successful commit
        if notify_msg:
             Notification.create_notification(
                 recipient_code=app.DRIVER_ID,
                 sender_code=current_user.USER_CODE,
                 message=notify_msg
             )
             db.session.commit() # Commit notification separately
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing application: {e}", "danger")

    return redirect(url_for("sponsor_bp.review_driver_applications"))


# --- Routes kept from previous merge (Admin only) ---

@sponsor_bp.route("/users/new", methods=["GET", "POST"])
@role_required(Role.ADMINISTRATOR)
def create_sponsor_user():
    if request.method == "GET":
        return render_template("sponsor/create_user.html")

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()
    org_name = (request.form.get("org_name") or "").strip()

    if not username or not email or not org_name:
        flash("Username, Email, and Organization Name are required.", "danger")
        return render_template("sponsor/create_user.html")

    if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
        flash("Username or email is already taken.", "danger")
        return render_template("sponsor/create_user.html", username=username, email=email, org_name=org_name)

    new_user_code = next_user_code()
    new_user = User(
        USER_CODE=new_user_code, USERNAME=username, USER_TYPE=Role.SPONSOR,
        FNAME=request.form.get("fname", "Sponsor"), LNAME=request.form.get("lname", "User"),
        EMAIL=email, CREATED_AT=datetime.utcnow(), IS_ACTIVE=1, IS_LOCKED_OUT=0, FAILED_ATTEMPTS=0,
    )
    temp_password = new_user.admin_set_new_pass()
    new_sponsor_profile = Sponsor(SPONSOR_ID=new_user_code, ORG_NAME=org_name, STATUS="Approved")

    db.session.add(new_user)
    db.session.add(new_sponsor_profile)

    try:
        db.session.commit()
        log_audit_event("ADMIN_CREATE_SPONSOR", f"by={current_user.USERNAME} new_user={username} org={org_name}")
        flash(f"Sponsor account '{username}' for {org_name} created. Temp Pass: {temp_password}", "success")
        return redirect(url_for("sponsor_bp.list_sponsor_users"))
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sponsor user: {e}")
        flash("Error creating sponsor user.", "danger")
        return render_template("sponsor/create_user.html", username=username, email=email, org_name=org_name)

@sponsor_bp.route("/users", methods=["GET"])
@role_required(Role.ADMINISTRATOR)
def list_sponsor_users():
    sponsors = User.query.filter_by(USER_TYPE=Role.SPONSOR).order_by(User.USERNAME.asc()).all()
    for sponsor_user in sponsors:
         sponsor_profile = Sponsor.query.get(sponsor_user.USER_CODE)
         sponsor_user.org_name = sponsor_profile.ORG_NAME if sponsor_profile else "N/A"
    return render_template("sponsor/list_users.html", users=sponsors)


# View Associated Drivers (Keep 'main' logic)
@sponsor_bp.route('/drivers', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def view_associated_drivers():
    associations = DriverSponsorAssociation.query.filter_by(sponsor_id=current_user.USER_CODE).all()
    drivers = []
    if associations:
        driver_ids = [assoc.driver_id for assoc in associations]
        drivers = User.query.filter(User.USER_CODE.in_(driver_ids)).all()
        points_map = {assoc.driver_id: assoc.points for assoc in associations}
        for driver in drivers:
            driver.sponsor_points = points_map.get(driver.USER_CODE, 0)
    return render_template('sponsor/drivers.html', drivers=drivers)


# --- Routes added from previous merge ---

# View Purchase History
@sponsor_bp.route('/purchase_history')
@role_required(Role.SPONSOR, allow_admin=True)
def purchase_history():
    purchases = Purchase.query.filter_by(
        sponsor_id=current_user.USER_CODE
    ).order_by(Purchase.purchase_date.desc()).all()
    for p in purchases:
        user = User.query.get(p.user_id)
        p.username = user.USERNAME if user else f"User ID {p.user_id}"
    return render_template('sponsor/purchase_history.html', purchases=purchases)


# View Driver Point History
@sponsor_bp.route('/driver_point_history')
@role_required(Role.SPONSOR, allow_admin=True)
def driver_point_history():
    sponsor_id_str = f"Sponsor ID: {current_user.USER_CODE}"
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS,
        AuditLog.DETAILS.like(f"%{sponsor_id_str}%")
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template('administrator/audit_list.html', # Or sponsor/audit_list.html
                           title="Driver Point History (Your Org)",
                           events=events)