# administrator/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_user, logout_user, login_required, current_user # Corrected import order
from common.decorators import role_required
# --- Merged Imports ---
from models import User, Role, AuditLog, db, Sponsor, Driver, Admin # Added Driver, Admin, Sponsor
from extensions import db # Keep this for SQLAlchemy instance access
from sqlalchemy import or_
# Combine logging constants and function import
from common.logging import (LOGIN_EVENT, SALES_BY_SPONSOR, SALES_BY_DRIVER,
                            INVOICE_EVENT, DRIVER_POINTS, log_audit_event)
from datetime import datetime, timedelta
import csv
from io import StringIO

# Blueprint definition
administrator_bp = Blueprint('administrator_bp', __name__, template_folder="../templates")

# --- Helper Functions ---

def parse_date(date_str):
    """Safely parse a YYYY-MM-DD string into a datetime object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

def next_user_code():
    """Generates the next available USER_CODE."""
    last_user = User.query.order_by(User.USER_CODE.desc()).first()
    return (last_user.USER_CODE + 1) if last_user else 1

# --- Audit Log Routes ---

@administrator_bp.get("/audit_logs/export")
@role_required(Role.ADMINISTRATOR) # Simplified decorator
def export_audit_csv():
    """Exports audit logs to CSV, with optional type and date filtering."""
    # Use filtering logic from 078d...
    event_type = request.args.get("event_type") or request.args.get("type") # Allow both param names
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    start_dt = parse_date(start_str)
    end_dt = parse_date(end_str)

    q = AuditLog.query # Start with base query

    if event_type:
        q = q.filter(AuditLog.EVENT_TYPE == event_type)
    if start_dt:
        q = q.filter(AuditLog.CREATED_AT >= start_dt)
    if end_dt:
        # Include events up to the end of the selected day
        q = q.filter(AuditLog.CREATED_AT < end_dt + timedelta(days=1))

    # Always order by date descending for consistency
    rows = q.order_by(AuditLog.CREATED_AT.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    # Corrected header row to match written data
    cw.writerow(["Timestamp", "Event Type", "Details", "Event ID"])
    for row in rows:
        cw.writerow([
            row.CREATED_AT.strftime("%Y-%m-%d %H:%M:%S UTC") if row.CREATED_AT else "",
            row.EVENT_TYPE or "",
            row.DETAILS or "",
            row.EVENT_ID or ""
        ])

    csv_bytes = si.getvalue().encode('utf-8')
    # Generate filename including date range if present
    date_range_str = ""
    if start_str or end_str:
        date_range_str = f"_from_{start_str or 'start'}_to_{end_str or 'end'}"
    filename = f"audit_logs_{event_type or 'all'}{date_range_str}_{datetime.now().strftime('%Y%m%d_%HM%S')}.csv"

    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=\"{filename}\""} # Quote filename
    )

@administrator_bp.route("/audit_logs")
@role_required(Role.ADMINISTRATOR)
def audit_menu():
    """Displays the main audit log menu."""
    # Pass event types for filtering options in the template
    event_types = [LOGIN_EVENT, SALES_BY_SPONSOR, SALES_BY_DRIVER, INVOICE_EVENT, DRIVER_POINTS] # Add others as needed
    return render_template("administrator/audit_menu.html", event_types=event_types)


# Specific Audit Log Views (simplified, use view_audit_logs with filter)
# These routes can be kept if direct links are desired, or removed in favor of filtering on view_audit_logs

@administrator_bp.route("/audit_logs/sales/sponsor")
@role_required(Role.ADMINISTRATOR)
def audit_sales_by_sponsor():
    return redirect(url_for(".view_audit_logs", event_type=SALES_BY_SPONSOR))

@administrator_bp.route("/audit_logs/sales/driver")
@role_required(Role.ADMINISTRATOR)
def audit_sales_by_driver():
     return redirect(url_for(".view_audit_logs", event_type=SALES_BY_DRIVER))

@administrator_bp.route("/audit_logs/invoices")
@role_required(Role.ADMINISTRATOR)
def audit_invoices():
     return redirect(url_for(".view_audit_logs", event_type=INVOICE_EVENT))

@administrator_bp.route("/audit_logs/driver-points")
@role_required(Role.ADMINISTRATOR)
def audit_driver_points():
     return redirect(url_for(".view_audit_logs", event_type=DRIVER_POINTS))


# Combined View Audit Logs Route (using filtering from 078d...)
@administrator_bp.get('/audit_logs/view')
@role_required(Role.ADMINISTRATOR)
def view_audit_logs():
    """Displays audit logs with filtering by type and date."""
    event_type = request.args.get("event_type") or request.args.get("type")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    allowed = {LOGIN_EVENT, SALES_BY_SPONSOR, SALES_BY_DRIVER, INVOICE_EVENT, DRIVER_POINTS} # Define allowed types
    if event_type and event_type not in allowed:
        flash("Invalid audit log type selected.", "warning")
        event_type = None # Clear invalid type

    q = AuditLog.query # Base query

    if event_type:
        q = q.filter(AuditLog.EVENT_TYPE == event_type)

    start_dt = parse_date(start_str)
    end_dt = parse_date(end_str)

    if start_dt:
        q = q.filter(AuditLog.CREATED_AT >= start_dt)
    if end_dt:
        q = q.filter(AuditLog.CREATED_AT < end_dt + timedelta(days=1))

    # Apply ordering and limit
    events = q.order_by(AuditLog.CREATED_AT.desc()).limit(500).all() # Use 'events' consistently

    # Titles mapping
    titles = {
        LOGIN_EVENT: "Login Activity",
        SALES_BY_SPONSOR: "Sales by Sponsor",
        SALES_BY_DRIVER: "Sales by Driver",
        INVOICE_EVENT: "Invoices",
        DRIVER_POINTS: "Driver Point Tracking",
    }
    title = titles.get(event_type, "All Audit Logs") # Default title

    return render_template(
        "administrator/audit_list.html",
        title=title,
        events=events, # Pass the queried events
        event_type=event_type, # Pass current filter type
        start=start_str, # Pass date filters back for display
        end=end_str,
        allowed_event_types=allowed # Pass allowed types for filter dropdown
    )


# --- Basic Admin Routes ---

# Login - Might be redundant if auth_bp handles all logins. Kept for now.
@administrator_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(USERNAME=username).first()

        # Ensure user is an admin
        if user and user.USER_TYPE == Role.ADMINISTRATOR and user.check_password(password):
            login_user(user)
            flash("Admin login successful!", "success")
            return redirect(url_for('administrator_bp.dashboard'))
        else:
            flash("Invalid admin username or password", "danger")

    return render_template('administrator/login.html') # Assumes admin-specific login template

# Dashboard
@administrator_bp.route('/dashboard')
@role_required(Role.ADMINISTRATOR)
def dashboard():
    return render_template('administrator/dashboard.html', user=current_user)

# Logout - Should ideally redirect to auth.logout
@administrator_bp.route('/logout')
@login_required
def logout():
    # It's better practice to have a single logout route in auth_bp
    return redirect(url_for('auth.logout'))


# --- User Management ---

# Add User (Using HEAD logic + admin_set_new_pass)
@administrator_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.ADMINISTRATOR)
def add_user():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        role = request.form.get('role')

        # Basic validation
        if not name or not email or not username or not role:
            flash("All fields are required.", "danger")
            return render_template('administrator/add_user.html', roles=Role.choices())
        if role not in Role.choices():
             flash("Invalid role selected.", "danger")
             return render_template('administrator/add_user.html', roles=Role.choices())


        # Split name (using HEAD's safer split)
        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "User" # Default last name

        # Check if user already exists
        if User.query.filter((User.USERNAME == username) | (User.EMAIL == email)).first():
            flash("Username or email already exists.", "danger")
            return render_template('administrator/add_user.html', roles=Role.choices(), name=name, email=email, username=username, selected_role=role)

        new_user_code = next_user_code()

        # Create base User
        new_user = User(
            USER_CODE=new_user_code,
            USERNAME=username,
            USER_TYPE=role,
            FNAME=first_name,
            LNAME=last_name,
            EMAIL=email,
            IS_LOCKED_OUT=0,
            CREATED_AT=datetime.utcnow(), # Use UTC
            IS_ACTIVE=1 # Default to active
        )
        # Use admin_set_new_pass
        new_pass = new_user.admin_set_new_pass()
        db.session.add(new_user)

        # Create role-specific profile (essential part from HEAD)
        try:
            if role == Role.DRIVER:
                # Get license from form, make it optional
                license_num = request.form.get('license_number', '').strip() or 'N/A'
                driver = Driver(DRIVER_ID=new_user.USER_CODE, LICENSE_NUMBER=license_num)
                db.session.add(driver)
            elif role == Role.SPONSOR:
                # Get org name from form, make it required for sponsors
                org_name = request.form.get('org_name', '').strip()
                if not org_name:
                    db.session.rollback() # Important: Rollback user creation if org_name missing
                    flash("Organization Name is required for Sponsors.", "danger")
                    return render_template('administrator/add_user.html', roles=Role.choices(), name=name, email=email, username=username, selected_role=role)
                sponsor = Sponsor(SPONSOR_ID=new_user.USER_CODE, ORG_NAME=org_name, STATUS="Approved") # Default approved if added by admin
                db.session.add(sponsor)
            elif role == Role.ADMINISTRATOR:
                # Get optional title from form
                role_title = request.form.get('role_title', '').strip() or 'Administrator'
                admin = Admin(ADMIN_ID=new_user.USER_CODE, ROLE_TITLE=role_title)
                db.session.add(admin)

            db.session.commit()

            # Log event
            log_audit_event("ADMIN_CREATE_USER", f"Admin {current_user.USERNAME} created user {username} (ID: {new_user_code}) with role {role}.")


            flash_message = (
                f"User '{username}' created successfully with role '{role}'. "
                f"🚨 **TEMPORARY PASSWORD:** `{new_pass}`. Please provide this securely. 🚨"
            )
            flash(flash_message, "warning")
            return redirect(url_for('administrator_bp.accounts')) # Redirect to accounts list

        except IntegrityError as e:
            db.session.rollback()
            flash(f"Database error creating user profile: {e}", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    # GET request
    return render_template('administrator/add_user.html', roles=Role.choices())


# --- Account Listing Routes ---

@administrator_bp.route('/accounts', methods=['GET'])
@role_required(Role.ADMINISTRATOR)
def accounts():
    """Lists all active user accounts."""
    search_term = request.args.get('search', '')
    query = User.query.filter_by(IS_ACTIVE=1)
    if search_term:
        search_like = f"%{search_term}%"
        query = query.filter(
            or_(
                User.USERNAME.like(search_like),
                User.FNAME.like(search_like),
                User.LNAME.like(search_like),
                User.EMAIL.like(search_like)
            )
        )
    users = query.order_by(User.USER_CODE.asc()).all()
    return render_template('administrator/accounts.html', accounts=users, search_term=search_term)

@administrator_bp.route('/disabled_accounts', methods=['GET'])
@role_required(Role.ADMINISTRATOR)
def disabled_accounts():
    """Lists all inactive/disabled user accounts."""
    users = User.query.filter_by(IS_ACTIVE=0).order_by(User.USER_CODE.asc()).all()
    return render_template('administrator/disabled_accounts.html', accounts=users)


# --- Account Locking/Unlocking ---

@administrator_bp.route('/locked_users', methods=['GET'])
@role_required(Role.ADMINISTRATOR)
def locked_users():
    """Lists users currently locked out (excluding admin timeouts)."""
    # Filter by lock status but exclude those locked by admin timeout if LOCKED_REASON is used
    locked_users = User.query.filter(User.IS_LOCKED_OUT == 1, User.LOCKED_REASON != 'admin').all()
    return render_template('administrator/locked_users.html', locked_users=locked_users)


@administrator_bp.route('/unlock/<int:user_id>', methods=['POST'])
@role_required(Role.ADMINISTRATOR)
def unlock(user_id):
    """Unlocks a user locked due to failed attempts."""
    user = User.query.get_or_404(user_id)
    user.clear_failed_attempts() # Resets attempts, lockout time, and flags
    # IS_LOCKED_OUT is cleared by clear_failed_attempts
    db.session.commit()
    log_audit_event("ADMIN_UNLOCK_USER", f"Admin {current_user.USERNAME} unlocked user {user.USERNAME} (ID: {user_id}).")
    flash(f'Account for {user.USERNAME} has been unlocked.', 'success')
    return redirect(request.referrer or url_for('administrator_bp.locked_users')) # Redirect back


@administrator_bp.route('/unlock_all', methods=['POST'])
@role_required(Role.ADMINISTRATOR)
def unlock_all():
    """Unlocks all users locked due to failed attempts."""
    locked_users = User.query.filter(User.IS_LOCKED_OUT == 1, User.LOCKED_REASON != 'admin').all()
    count = 0
    for user in locked_users:
        user.clear_failed_attempts()
        count += 1
    if count > 0:
        db.session.commit()
        log_audit_event("ADMIN_UNLOCK_ALL", f"Admin {current_user.USERNAME} unlocked {count} accounts.")
        flash(f'{count} locked accounts have been unlocked.', 'success')
    else:
        flash('No accounts needed unlocking.', 'info')
    return redirect(url_for('administrator_bp.locked_users'))


# --- Account Editing/Disabling/Enabling ---

@administrator_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@role_required(Role.ADMINISTRATOR)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.USER_CODE == current_user.USER_CODE:
        flash("You cannot edit your own account via this form.", "danger")
        return redirect(url_for('administrator_bp.accounts'))

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_email = request.form.get('email', '').strip()
        new_fname = request.form.get('fname', '').strip()
        new_lname = request.form.get('lname', '').strip()
        new_user_type = request.form.get('user_type')

        # Validation
        if not all([new_username, new_email, new_fname, new_lname, new_user_type]):
             flash("All fields must be filled.", "danger")
             return render_template('administrator/edit_user.html', user=user, roles=Role.choices())
        if new_user_type not in Role.choices():
             flash("Invalid role selected.", "danger")
             return render_template('administrator/edit_user.html', user=user, roles=Role.choices())


        # Check for duplicates (excluding self)
        username_check = User.query.filter(User.USERNAME == new_username, User.USER_CODE != user_id).first()
        if username_check:
            flash(f"Username '{new_username}' is already taken.", "danger")
            return render_template('administrator/edit_user.html', user=user, roles=Role.choices()) # Show form again

        email_check = User.query.filter(User.EMAIL == new_email, User.USER_CODE != user_id).first()
        if email_check:
            flash(f"Email '{new_email}' is already in use.", "danger")
            return render_template('administrator/edit_user.html', user=user, roles=Role.choices())

        # Track changes for logging
        changes = []
        if user.USERNAME != new_username: changes.append(f"Username ('{user.USERNAME}' -> '{new_username}')")
        if user.EMAIL != new_email: changes.append(f"Email ('{user.EMAIL}' -> '{new_email}')")
        if user.FNAME != new_fname: changes.append(f"First Name ('{user.FNAME}' -> '{new_fname}')")
        if user.LNAME != new_lname: changes.append(f"Last Name ('{user.LNAME}' -> '{new_lname}')")
        if user.USER_TYPE != new_user_type: changes.append(f"Role ('{user.USER_TYPE}' -> '{new_user_type}')")


        try:
            user.USERNAME = new_username
            user.EMAIL = new_email
            user.FNAME = new_fname
            user.LNAME = new_lname
            # Note: Changing USER_TYPE might require updating/creating Driver/Sponsor/Admin records.
            # This logic is complex and not fully handled here. Add checks/updates if needed.
            if user.USER_TYPE != new_user_type:
                 flash(f"Warning: Role changed from {user.USER_TYPE} to {new_user_type}. Associated profile (Driver/Sponsor/Admin) may need manual adjustment.", "warning")
                 user.USER_TYPE = new_user_type

            db.session.commit()
            if changes:
                 log_audit_event("ADMIN_EDIT_USER", f"Admin {current_user.USERNAME} edited user {user.USERNAME} (ID: {user_id}). Changes: {'; '.join(changes)}.")
            flash(f'User {user.USERNAME} updated successfully!', 'success')
            return redirect(url_for('administrator_bp.accounts'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
            # Render form again on error
            return render_template('administrator/edit_user.html', user=user, roles=Role.choices())

    # GET request
    return render_template('administrator/edit_user.html', user=user, roles=Role.choices())


@administrator_bp.route('/disable_user/<int:user_id>', methods=['POST'])
@role_required(Role.ADMINISTRATOR)
def disable_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.USER_CODE == current_user.USER_CODE:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for('administrator_bp.accounts'))

    if user.IS_ACTIVE == 0:
        flash(f"User {user.USERNAME} is already disabled.", "warning")
    else:
        user.IS_ACTIVE = 0
        user.clear_failed_attempts() # Also clear locks when disabling
        db.session.commit()
        log_audit_event("ADMIN_DISABLE_USER", f"Admin {current_user.USERNAME} disabled user {user.USERNAME} (ID: {user_id}).")
        flash(f'User {user.USERNAME} has been disabled.', 'info')

    # Redirect back to the page the admin came from (active or disabled list)
    return redirect(request.referrer or url_for('administrator_bp.accounts'))


@administrator_bp.route('/enable_user/<int:user_id>', methods=['POST'])
@role_required(Role.ADMINISTRATOR)
def enable_user(user_id):
    user = User.query.get_or_404(user_id)

    # Cannot enable self (already active if logged in)
    if user.USER_CODE == current_user.USER_CODE:
         return redirect(url_for('administrator_bp.accounts'))


    if user.IS_ACTIVE == 1:
        flash(f"User {user.USERNAME} is already enabled.", "warning")
    else:
        user.IS_ACTIVE = 1
        user.clear_failed_attempts() # Clear any residual locks
        db.session.commit()
        log_audit_event("ADMIN_ENABLE_USER", f"Admin {current_user.USERNAME} enabled user {user.USERNAME} (ID: {user_id}).")
        flash(f'User {user.USERNAME} has been enabled.', 'success')

    return redirect(request.referrer or url_for('administrator_bp.disabled_accounts'))


@administrator_bp.route('/reset_user_password/<int:user_id>', methods=['POST'])
@role_required(Role.ADMINISTRATOR)
def reset_user_password(user_id):
    """Resets a user's password and flashes a temporary one."""
    user = User.query.get_or_404(user_id)

    # Optional: Prevent resetting own password this way?
    # if user.USER_CODE == current_user.USER_CODE:
    #    flash("Use the 'Change Password' option in your settings.", "warning")
    #    return redirect(url_for('administrator_bp.edit_user', user_id=user_id))


    try:
        new_pass = user.admin_set_new_pass() # Use the correct method
        user.clear_failed_attempts() # Unlock account on password reset
        db.session.commit()

        log_audit_event("ADMIN_RESET_PASSWORD", f"Admin {current_user.USERNAME} reset password for user {user.USERNAME} (ID: {user_id}).")

        # Flash temporary password (use secure delivery in production)
        flash_message = (
            f"Password for user '{user.USERNAME}' reset. "
            f"🚨 **TEMPORARY PASSWORD:** `{new_pass}`. Provide securely. 🚨"
        )
        flash(flash_message, "warning")
    except Exception as e:
         db.session.rollback()
         flash(f"Error resetting password: {e}", "danger")


    return redirect(url_for('administrator_bp.edit_user', user_id=user_id))

# --- Sponsor Review Routes (Keep the version from 'main' which is more complete) ---

@administrator_bp.route("/sponsors/pending") # More specific route
@role_required(Role.ADMINISTRATOR)
def review_sponsors():
    """Lists pending sponsor applications for admin review."""
    # Join with User to get names easily
    pending_sponsors = db.session.query(Sponsor, User).join(User, Sponsor.SPONSOR_ID == User.USER_CODE).filter(Sponsor.STATUS == "Pending").all()
    # Ensure the correct template name is used
    return render_template("administrator/review_sponsors.html", sponsors=pending_sponsors)


@administrator_bp.route("/sponsors/<int:sponsor_id>/<decision>", methods=['POST']) # Should be POST
@role_required(Role.ADMINISTRATOR)
def sponsor_decision(sponsor_id, decision):
    """Processes admin decision (approve/reject) on a sponsor."""
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    sponsor_user = User.query.get(sponsor_id) # For logging/notifications
    username = sponsor_user.USERNAME if sponsor_user else f"ID {sponsor_id}"

    if decision.lower() == "approve":
        sponsor.STATUS = "Approved"
        action_past = "approved"
        # Optional: Activate the user account if it wasn't already
        if sponsor_user and sponsor_user.IS_ACTIVE == 0:
            sponsor_user.IS_ACTIVE = 1
        # Notify sponsor
        Notification.create_notification(recipient_code=sponsor_id, sender_code=current_user.USER_CODE, message="Your sponsor application has been approved.")

    elif decision.lower() == "reject":
        sponsor.STATUS = "Rejected"
        action_past = "rejected"
        # Optional: Disable the user account if rejecting
        # if sponsor_user:
        #    sponsor_user.IS_ACTIVE = 0
        # Notify sponsor
        Notification.create_notification(recipient_code=sponsor_id, sender_code=current_user.USER_CODE, message="Your sponsor application has been rejected.")
    else:
        flash("Invalid decision specified.", "danger")
        return redirect(url_for("administrator_bp.review_sponsors"))

    try:
        db.session.commit()
        log_audit_event("ADMIN_SPONSOR_REVIEW", f"Admin {current_user.USERNAME} {action_past} sponsor {username} (ID: {sponsor_id}).")
        flash(f"Sponsor {username} {action_past}!", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing sponsor decision: {e}", "danger")

    return redirect(url_for("administrator_bp.review_sponsors"))


# --- User Timeout Routes (from HEAD / main) ---

@administrator_bp.get("/timeouts")
@role_required(Role.ADMINISTRATOR)
def timeout_users():
    """Displays interface for manually timing out users."""
    # Filter out the current admin to prevent self-timeout via this UI
    users = User.query.filter(User.USER_CODE != current_user.USER_CODE).order_by(User.USERNAME.asc()).all()
    return render_template("administrator/timeout_users.html", users=users) # Needs this template

@administrator_bp.post("/set_timeout/<int:user_id>")
@role_required(Role.ADMINISTRATOR)
def set_timeout(user_id):
    """Applies a timed lockout to a user account."""
    user = User.query.get_or_404(user_id)

    # Prevent self-timeout
    if user.USER_CODE == current_user.USER_CODE:
        flash("You cannot time out your own account.", "danger")
        return redirect(url_for("administrator_bp.timeout_users"))


    try:
        minutes = int(request.form.get("minutes", 0))
        if minutes <= 0:
            flash("Timeout duration must be a positive number of minutes.", "danger")
            return redirect(url_for("administrator_bp.timeout_users"))
    except ValueError:
        flash("Invalid duration entered.", "danger")
        return redirect(url_for("administrator_bp.timeout_users"))

    user.IS_LOCKED_OUT = 1
    user.LOCKOUT_TIME = datetime.utcnow() + timedelta(minutes=minutes)
    user.LOCKED_REASON = "admin" # Mark as admin-initiated timeout
    db.session.commit()

    log_audit_event("ADMIN_TIMEOUT", f"Admin {current_user.USERNAME} timed out user {user.USERNAME} (ID: {user_id}) for {minutes} minutes.")
    flash(f"User {user.USERNAME} has been timed out until {user.LOCKOUT_TIME.strftime('%Y-%m-%d %H:%M:%S UTC')}.", "info")
    return redirect(url_for("administrator_bp.timeout_users"))

@administrator_bp.route("/clear_timeout/<int:user_id>", methods=["POST"])
@role_required(Role.ADMINISTRATOR) # Ensure only admins can clear
def clear_timeout(user_id):
    """Clears an admin-initiated timeout."""
    user = User.query.get_or_404(user_id)

    # Only clear if it was an admin timeout
    if user.IS_LOCKED_OUT == 1 and user.LOCKED_REASON == "admin":
        user.clear_failed_attempts() # This also clears IS_LOCKED_OUT, LOCKOUT_TIME, LOCKED_REASON
        db.session.commit()
        log_audit_event("ADMIN_CLEAR_TIMEOUT", f"Admin {current_user.USERNAME} cleared timeout for user {user.USERNAME} (ID: {user_id}).")
        flash(f"Admin timeout cleared for user {user.USERNAME}.", "success")
    else:
        flash(f"User {user.USERNAME} was not under an admin timeout.", "warning")

    return redirect(url_for("administrator_bp.timeout_users"))