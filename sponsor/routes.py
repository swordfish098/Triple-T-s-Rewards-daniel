# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-72ca7a46f1915a7f669f3692e9b77d23b248eaee/sponsor/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, DRIVER_POINTS
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import User, Role, StoreSettings, db, DriverApplication, Sponsor, Notification, Driver, DriverSponsorAssociation, Purchase
from extensions import db
import secrets
import string

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

def next_user_code():
    last_user = User.query.order_by(User.USER_CODE.desc()).first()
    return (last_user.USER_CODE + 1) if last_user else 1

# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    return render_template('sponsor/dashboard.html')

# Update Store Settings (now sponsor-specific)
@sponsor_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    settings = StoreSettings.query.filter_by(sponsor_id=current_user.USER_CODE).first()
    if not settings:
        settings = StoreSettings(sponsor_id=current_user.USER_CODE)
        db.session.add(settings)

    if request.method == 'POST':
        settings.ebay_category_id = request.form.get('ebay_category_id')
        settings.point_ratio = int(request.form.get('point_ratio'))
        db.session.commit()
        flash("Store settings updated successfully!", "success")
        return redirect(url_for('sponsor_bp.update_settings'))

    return render_template("sponsor/settings.html", settings=settings)

# Manage points page
@sponsor_bp.route('/points', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points_page():
    associations = DriverSponsorAssociation.query.filter_by(sponsor_id=current_user.USER_CODE).all()
    for assoc in associations:
        # We access the User by the DRIVER_ID on the association model
        assoc.user = User.query.get(assoc.driver_id)
    return render_template('sponsor/points.html', drivers=associations)

# Manage points for a specific driver-sponsor relationship
@sponsor_bp.route('/points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points(driver_id):
    association = DriverSponsorAssociation.query.get((driver_id, current_user.USER_CODE))
    if not association:
        flash("Driver is not associated with your organization.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    driver_user = User.query.get(driver_id)
    username = driver_user.USERNAME if driver_user else "Unknown Driver"

    action = request.form.get('action')
    points = request.form.get('points', type=int)
    reason = request.form.get('reason', '').strip() or "No reason provided."

    if not action or action not in ("award", "remove") or points is None or points <= 0:
        flash("Invalid request.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    log_message = ""
    notification_message = ""

    if action == "award":
        association.points += points
        log_message = f"Awarded {points} points to driver {username} (ID: {driver_id}). Reason: {reason}. Sponsor ID: {current_user.USER_CODE}."
        notification_message = f"🎉 **{current_user.FNAME} {current_user.LNAME}** awarded you {points} points! New balance: {association.points}."
        flash(f"Awarded {points} points to {username}.", "success")
    elif action == "remove":
        association.points -= points
        log_message = f"Removed {points} points from driver {username} (ID: {driver_id}). Reason: {reason}. Sponsor ID: {current_user.USER_CODE}."
        notification_message = f"⚠️ **{current_user.FNAME} {current_user.LNAME}** removed {points} points. New balance: {association.points}."
        flash(f"Removed {points} points from {username}.", "info")

    from models import AuditLog # If not already imported
    log_entry = AuditLog(
        EVENT_TYPE="DRIVER_POINTS", # Use DRIVER_POINTS from common.logging
        DETAILS=log_message
    )
    db.session.add(log_entry)

    if driver_user and driver_user.wants_point_notifications:
        Notification.create_notification(
            recipient_code=driver_id,
            sender_code=current_user.USER_CODE,
            message=notification_message
        )

    db.session.commit()
    return redirect(url_for('sponsor_bp.manage_points_page'))

# Add a New Driver (with automatic association)
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        license_number = request.form.get('license_number', '000000')

        if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))
        
        new_user_code = next_user_code()

        new_user = User(
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
        new_pass = new_user.admin_set_new_pass()
        db.session.add(new_user)

        db.session.flush()

       # Now, create the corresponding Driver profile record at the same time
        new_driver_profile = Driver(
            DRIVER_ID=new_user_code,
            LICENSE_NUMBER=license_number
        )
        db.session.add(new_driver_profile) # Add the new driver profile to the session
        
        # Also create the automatic association to the sponsor who created them
        association = DriverSponsorAssociation(
            driver_id=new_user_code,
            sponsor_id=current_user.USER_CODE
        )

        db.session.add(association)

        db.session.commit()
        flash(f"Driver '{username}' created and automatically associated with your organization. Temp Pass: {new_pass}", "success")
        return redirect(url_for('sponsor_bp.dashboard'))
        
    return render_template('sponsor/add_user.html')

# Driver application review (with association creation on approval)
@sponsor_bp.route("/applications")
@login_required
@role_required(Role.SPONSOR)
def review_driver_applications():
    apps = DriverApplication.query.filter_by(SPONSOR_ID=current_user.USER_CODE, STATUS="Pending").all()
    return render_template("sponsor/review_driver_applications.html", applications=apps)

@sponsor_bp.route("/applications/<int:app_id>/<decision>", methods=['GET', 'POST'])
@login_required
@role_required(Role.SPONSOR)
def driver_decision(app_id, decision):
    app = DriverApplication.query.get_or_404(app_id)
    if decision == "accept":
        app.STATUS = "Accepted"
        
        existing_assoc = DriverSponsorAssociation.query.get((app.DRIVER_ID, app.SPONSOR_ID))
        if not existing_assoc:
            association = DriverSponsorAssociation(
                driver_id=app.DRIVER_ID,
                sponsor_id=app.SPONSOR_ID
            )
            db.session.add(association)
    else:
        app.STATUS = "Rejected"

    db.session.commit()
    flash(f"Driver application {decision}ed!", "info")
    return redirect(url_for("sponsor_bp.review_driver_applications"))