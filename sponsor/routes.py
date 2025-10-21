# triple-ts-rewards/.../sponsor/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, DRIVER_POINTS
from datetime import datetime
from sqlalchemy.exc import IntegrityError
# --- Merged Imports ---
# Kept DriverSponsorAssociation, Purchase, and Driver from HEAD
# Kept AuditLog from the point history addition in HEAD
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

# Keeping generate_temp_password from upstream, might be useful elsewhere
def generate_temp_password(length: int = 10) -> str:
    """Generates a random temporary password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

# --- Routes ---

# Dashboard (Same in both)
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    return render_template('sponsor/dashboard.html')

# Update Store Settings (Using sponsor-specific logic from HEAD)
@sponsor_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    # Fetch or create settings specific to the current sponsor
    settings = StoreSettings.query.filter_by(sponsor_id=current_user.USER_CODE).first()
    if not settings:
        settings = StoreSettings(sponsor_id=current_user.USER_CODE)
        db.session.add(settings)
        # Commit here if creating, so the form has an object ID if needed
        # Or commit together with updates below. Let's commit with updates.

    if request.method == 'POST':
        # Consider adding validation (e.g., ensure point_ratio is > 0)
        settings.ebay_category_id = request.form.get('ebay_category_id', '2984') # Default if empty
        try:
            point_ratio_val = int(request.form.get('point_ratio', 10)) # Default if empty/invalid
            if point_ratio_val <= 0:
                flash("Point ratio must be a positive number.", "warning")
            else:
                settings.point_ratio = point_ratio_val
        except ValueError:
             flash("Invalid point ratio provided. Please enter a number.", "danger")
             # Don't commit if conversion fails, render form again
             return render_template("sponsor/settings.html", settings=settings)

        try:
            db.session.commit()
            flash("Store settings updated successfully!", "success")
            # Redirect only on successful commit
            return redirect(url_for('sponsor_bp.update_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating settings: {e}", "danger")

    return render_template("sponsor/settings.html", settings=settings)

# Manage points page (Using DriverSponsorAssociation logic from HEAD)
@sponsor_bp.route('/points', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points_page():
    # Fetch associations specific to the current sponsor
    sort_by = request.args.get('sort_by') # Get sort parameter
    query = DriverSponsorAssociation.query.filter_by(sponsor_id=current_user.USER_CODE)

    # Apply sorting
    if sort_by == 'points_desc':
        query = query.order_by(DriverSponsorAssociation.points.desc())
    elif sort_by == 'points_asc':
        query = query.order_by(DriverSponsorAssociation.points.asc())
    # Add sorting by name if needed
    # elif sort_by == 'name_asc':
    #    query = query.join(User, DriverSponsorAssociation.driver_id == User.USER_CODE).order_by(User.USERNAME.asc())
    else:
        # Default sort by driver ID
        query = query.order_by(DriverSponsorAssociation.driver_id.asc())


    associations = query.all()

    # Attach user info to each association for display in the template
    for assoc in associations:
        assoc.user = User.query.get(assoc.driver_id) # Get User object using driver_id

    return render_template('sponsor/points.html',
                           drivers=associations, # Pass associations, template expects 'drivers'
                           current_sort=sort_by)

# Manage points for a specific driver-sponsor relationship (Using HEAD logic)
@sponsor_bp.route('/points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points(driver_id):
    # Get the specific association
    association = DriverSponsorAssociation.query.get((driver_id, current_user.USER_CODE))
    if not association:
        flash("Driver is not associated with your organization.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    driver_user = User.query.get(driver_id)
    # Fallback if user somehow deleted but association remains
    username = driver_user.USERNAME if driver_user else f"Driver ID {driver_id}"

    action = request.form.get('action')
    try:
        points = int(request.form.get('points', 0)) # Default to 0 if invalid/missing
    except ValueError:
        flash("Invalid point amount entered.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    reason = request.form.get('reason', '').strip() or "No reason provided." # Default reason

    # Validation
    if action not in ("award", "remove") or points <= 0:
        flash("Invalid action or point amount (must be positive).", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    log_message = ""
    notification_message = ""
    original_points = association.points # For notification

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

    # Use AuditLog model (added in combined imports)
    log_entry = AuditLog(
        EVENT_TYPE=DRIVER_POINTS, # Constant from common.logging
        DETAILS=log_message,
        CREATED_AT=datetime.utcnow() # Explicitly set timestamp
    )
    db.session.add(log_entry)

    # Send notification if driver wants them
    if driver_user and driver_user.wants_point_notifications:
        try:
            Notification.create_notification(
                recipient_code=driver_id,
                sender_code=current_user.USER_CODE,
                message=notification_message
            )
        except Exception as e:
            # Log notification error but proceed with point change
            print(f"Error sending notification: {e}")
            flash("Points updated, but failed to send notification.", "warning")


    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating points: {e}", "danger")

    return redirect(url_for('sponsor_bp.manage_points_page'))

# Add a New Driver (Using HEAD logic with automatic association)
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        # Make license number optional, default to None if empty
        license_number = request.form.get('license_number', '').strip() or None

        # Validate required fields
        if not username or not email:
            flash("Username and Email are required.", "danger")
            return render_template('sponsor/add_user.html') # Re-render form

        # Check for existing user
        if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
            flash("Username or email already exists.", "danger")
            return render_template('sponsor/add_user.html', username=username, email=email, license_number=license_number) # Re-render form with old values

        new_user_code = next_user_code()

        # Create the User record
        new_user = User(
            USER_CODE=new_user_code,
            USERNAME=username,
            EMAIL=email,
            USER_TYPE=Role.DRIVER,
            FNAME="New", # Consider adding fields to the form for FNAME/LNAME
            LNAME="Driver",
            CREATED_AT=datetime.utcnow(),
            IS_ACTIVE=1, # Default to active
            IS_LOCKED_OUT=0 # Default to unlocked
            # Points are handled by association, no need for POINTS=0 here
        )
        # Generate and set temporary password using admin_set_new_pass from User model
        try:
            new_pass = new_user.admin_set_new_pass()
        except AttributeError:
             flash("Error: admin_set_new_pass method not found on User model.", "danger")
             return render_template('sponsor/add_user.html', username=username, email=email, license_number=license_number)


        db.session.add(new_user)

        # Create the corresponding Driver profile record
        new_driver_profile = Driver(
            DRIVER_ID=new_user_code,
            # Use provided license number, handle if None
            LICENSE_NUMBER=license_number if license_number else 'N/A' # Store 'N/A' or similar if not provided
        )
        db.session.add(new_driver_profile)

        # Create the automatic association to the sponsor who created them
        association = DriverSponsorAssociation(
            driver_id=new_user_code,
            sponsor_id=current_user.USER_CODE,
            points=0 # Start with 0 points for this sponsor
        )
        db.session.add(association)

        try:
            db.session.commit()
            flash(f"Driver '{username}' created and automatically associated. Temp Pass: {new_pass}", "success")
            # Redirect to the points management page or dashboard after success
            return redirect(url_for('sponsor_bp.manage_points_page'))
        except IntegrityError as e:
             db.session.rollback()
             flash(f"Database error: Could not create driver. {e}", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    # GET request: Show the form
    return render_template('sponsor/add_user.html')

# Driver application review (Using HEAD logic with association creation)
@sponsor_bp.route("/applications")
@login_required
@role_required(Role.SPONSOR) # Keep sponsor-only restriction
def review_driver_applications():
    # Fetch pending applications for this sponsor
    apps = DriverApplication.query.filter_by(
        SPONSOR_ID=current_user.USER_CODE,
        STATUS="Pending"
    ).all()
    # Add driver names to applications for display
    for app in apps:
        driver_user = User.query.get(app.DRIVER_ID)
        app.driver_name = driver_user.USERNAME if driver_user else f"ID: {app.DRIVER_ID}"
    return render_template("sponsor/review_driver_applications.html", applications=apps)

# Process driver application decision (Using HEAD logic)
@sponsor_bp.route("/applications/<int:app_id>/<decision>", methods=['POST']) # Should be POST
@login_required
@role_required(Role.SPONSOR) # Keep sponsor-only restriction
def driver_decision(app_id, decision):
    app = DriverApplication.query.get_or_404(app_id)

    # Ensure the sponsor owns this application
    if app.SPONSOR_ID != current_user.USER_CODE:
        flash("You are not authorized to process this application.", "danger")
        return redirect(url_for("sponsor_bp.review_driver_applications"))

    if decision.lower() == "accept":
        app.STATUS = "Accepted"

        # Create association if it doesn't exist
        existing_assoc = DriverSponsorAssociation.query.get((app.DRIVER_ID, app.SPONSOR_ID))
        if not existing_assoc:
            association = DriverSponsorAssociation(
                driver_id=app.DRIVER_ID,
                sponsor_id=app.SPONSOR_ID,
                points=0 # Start with 0 points
            )
            db.session.add(association)
            flash_msg = f"Driver application accepted and association created!"
        else:
             flash_msg = f"Driver application accepted (association already exists)."

        # Notify driver
        Notification.create_notification(
            recipient_code=app.DRIVER_ID,
            sender_code=current_user.USER_CODE,
            message=f"🎉 Your application to {current_user.FNAME} {current_user.LNAME}'s organization has been accepted!"
        )

    elif decision.lower() == "reject":
        app.STATUS = "Rejected"
        flash_msg = f"Driver application rejected."
        # Optionally get reason from form: reason = request.form.get('rejection_reason', '')
        # app.REASON = reason # If you add a reason field to the application model

        # Notify driver
        Notification.create_notification(
            recipient_code=app.DRIVER_ID,
            sender_code=current_user.USER_CODE,
            message=f"ℹ️ Your application to {current_user.FNAME} {current_user.LNAME}'s organization has been rejected." # Add reason if available
        )
    else:
        flash("Invalid decision.", "warning")
        return redirect(url_for("sponsor_bp.review_driver_applications"))

    try:
        db.session.commit()
        flash(flash_msg, "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing application: {e}", "danger")

    return redirect(url_for("sponsor_bp.review_driver_applications"))


# --- Routes kept from upstream (078d...) ---
# Note: These manage SPONSOR users, not drivers associated with a sponsor.
# They might be better placed in the administrator blueprint depending on requirements.

@sponsor_bp.route("/users/new", methods=["GET", "POST"]) # Renamed route slightly
@role_required(Role.ADMINISTRATOR) # Changed: Only Admins should create Sponsors
def create_sponsor_user():
    if request.method == "GET":
        return render_template("sponsor/create_user.html") # Needs this template

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip() # Assuming email is collected
    org_name = (request.form.get("org_name") or "").strip() # Assuming org_name is collected

    if not username or not email or not org_name:
        flash("Username, Email, and Organization Name are required.", "danger")
        return render_template("sponsor/create_user.html")

    if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
        flash("Username or email is already taken.", "danger")
        return render_template("sponsor/create_user.html", username=username, email=email, org_name=org_name)

    new_user_code = next_user_code()
    new_user = User(
        USER_CODE=new_user_code,
        USERNAME=username,
        USER_TYPE=Role.SPONSOR,
        FNAME=request.form.get("fname", "Sponsor"), # Get from form or use default
        LNAME=request.form.get("lname", "User"),   # Get from form or use default
        EMAIL=email,
        CREATED_AT=datetime.utcnow(),
        IS_ACTIVE=1,
        IS_LOCKED_OUT=0,
        FAILED_ATTEMPTS=0,
    )
    temp_password = new_user.admin_set_new_pass() # Use the better password generator

    # Create Sponsor profile
    new_sponsor_profile = Sponsor(
        SPONSOR_ID=new_user_code,
        ORG_NAME=org_name,
        STATUS="Approved" # New sponsors created by admin are likely approved
    )

    db.session.add(new_user)
    db.session.add(new_sponsor_profile)

    try:
        db.session.commit()
        log_audit_event("ADMIN_CREATE_SPONSOR", f"by={current_user.USERNAME} new_user={username} org={org_name}")
        flash(f"Sponsor account '{username}' for {org_name} created. Temp Pass: {temp_password}", "success")
        return redirect(url_for("sponsor_bp.list_sponsor_users")) # Redirect to list view
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sponsor user: {e}") # Log detailed error
        flash("Error creating sponsor user.", "danger")
        return render_template("sponsor/create_user.html", username=username, email=email, org_name=org_name)

@sponsor_bp.route("/users", methods=["GET"]) # Renamed route slightly
@role_required(Role.ADMINISTRATOR) # Changed: Only Admins view all sponsors
def list_sponsor_users():
    sponsors = User.query.filter_by(USER_TYPE=Role.SPONSOR).order_by(User.USERNAME.asc()).all()
    # Add Org Name for display
    for sponsor_user in sponsors:
         sponsor_profile = Sponsor.query.get(sponsor_user.USER_CODE)
         sponsor_user.org_name = sponsor_profile.ORG_NAME if sponsor_profile else "N/A"
    return render_template("sponsor/list_users.html", users=sponsors) # Needs this template


# View Associated Drivers (Modified from upstream `driver_management`)
@sponsor_bp.route('/drivers', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def view_associated_drivers():
    """Shows drivers currently associated with the sponsor."""
    associations = DriverSponsorAssociation.query.filter_by(sponsor_id=current_user.USER_CODE).all()
    drivers = []
    if associations:
        driver_ids = [assoc.driver_id for assoc in associations]
        drivers = User.query.filter(User.USER_CODE.in_(driver_ids)).all()
        # Optionally add points from association to driver object for template
        points_map = {assoc.driver_id: assoc.points for assoc in associations}
        for driver in drivers:
            driver.sponsor_points = points_map.get(driver.USER_CODE, 0)

    # Reusing a template name, ensure it works with the User list + sponsor_points
    return render_template('sponsor/drivers.html', drivers=drivers)


# --- Routes added from HEAD ---

# View Purchase History (Sponsor-specific view)
@sponsor_bp.route('/purchase_history')
@role_required(Role.SPONSOR, allow_admin=True)
def purchase_history():
    """Retrieves all purchase records associated with the current sponsor's store."""
    purchases = Purchase.query.filter_by(
        sponsor_id=current_user.USER_CODE
    ).order_by(Purchase.purchase_date.desc()).all()

    # Add usernames to purchases for display
    for p in purchases:
        user = User.query.get(p.user_id)
        p.username = user.USERNAME if user else f"User ID {p.user_id}"

    # Assumes templates/sponsor/purchase_history.html exists
    return render_template('sponsor/purchase_history.html', purchases=purchases)


# View Driver Point History (Sponsor-specific view)
@sponsor_bp.route('/driver_point_history')
@role_required(Role.SPONSOR, allow_admin=True)
def driver_point_history():
    """Retrieves DRIVER_POINTS audit log entries relevant to the current sponsor."""
    # Filter audit logs for events related to this sponsor
    sponsor_id_str = f"Sponsor ID: {current_user.USER_CODE}"
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS,
        AuditLog.DETAILS.like(f"%{sponsor_id_str}%") # Filter details string
    ).order_by(AuditLog.CREATED_AT.desc()).all()

    # Re-use admin template or create a sponsor-specific one
    return render_template('administrator/audit_list.html', # Or sponsor/audit_list.html
                           title="Driver Point History (Your Org)",
                           events=events)