from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from models import User, Role, AuditLog
from extensions import db
from sqlalchemy import or_
from common.logging import (LOGIN_EVENT,
    SALES_BY_SPONSOR, SALES_BY_DRIVER, INVOICE_EVENT,
    DRIVER_POINTS)


# Blueprint for administrator-related routes
administrator_bp = Blueprint('administrator_bp', __name__, template_folder="../templates")

@administrator_bp.route("/audit_logs")
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def audit_menu():
    return render_template("administrator/audit_menu.html")
@administrator_bp.route("/audit_logs/sales/sponsor")
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def audit_sales_by_sponsor():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == SALES_BY_SPONSOR
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("administrator/audit_list.html",
                           title="Sales by Sponsor",
                           events=events)

@administrator_bp.route("/audit_logs/sales/driver")
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def audit_sales_by_driver():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == SALES_BY_DRIVER
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("administrator/audit_list.html",
                           title="Sales by Driver",
                           events=events)

@administrator_bp.route("/audit_logs/invoices")
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def audit_invoices():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == INVOICE_EVENT
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("administrator/audit_list.html",
                           title="Invoices",
                           events=events)

@administrator_bp.route("/audit_logs/driver-points")
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def audit_driver_points():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("administrator/audit_list.html",
                           title="Driver Point Tracking",
                           events=events)


# Login
@administrator_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Look up user by USERNAME
        user = User.query.filter_by(USERNAME=username).first()

        # Check password with bcrypt
        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('administrator_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    # Looks inside templates/administrator/login.html
    return render_template('administrator/login.html')

# Dashboard
@administrator_bp.route('/dashboard')
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def dashboard():
    # Looks inside templates/administrator/dashboard.html
    return render_template('administrator/dashboard.html', user=current_user)

@administrator_bp.get('/audit_logs/view')
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def view_audit_logs():
    event_type = request.args.get("event_type")
    allowed = {LOGIN_EVENT, SALES_BY_SPONSOR, SALES_BY_DRIVER, INVOICE_EVENT, DRIVER_POINTS}
    if event_type not in allowed:
        flash("Unknown audit log type.", "warning")
        return redirect(url_for("administrator_bp.audit_menu"))
    

    logs = (AuditLog.query
            .filter(AuditLog.EVENT_TYPE == event_type)
            .order_by(AuditLog.CREATED_AT.desc())
            .limit(200)
            .all())

    # Nice page title
    titles = {
        LOGIN_EVENT: "Login Activity",
        SALES_BY_SPONSOR: "Sales by Sponsor",
        SALES_BY_DRIVER: "Sales by Driver",
        INVOICE_EVENT: "Invoices",
        DRIVER_POINTS: "Driver Point Tracking",
    }
    return render_template(
        "administrator/audit_list.html",
        title=titles.get(event_type, "Unknown Event"),
        events=logs
    )

# Logout
@administrator_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

# Add User
@administrator_bp.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        # Check if the user already exists
        existing_user = User.query.filter_by(USERNAME=username).first()
        if existing_user:
            flash("Username already exists.", "danger")
            return redirect(url_for('administrator_bp.add_user'))

        # Find the highest existing USER_CODE and increment it
        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            # Starting code for the first user if the table is empty
            new_user_code = 1
        
        # Create a new User instance with the generated USER_CODE and hashed password
        new_user = User(
            USER_CODE=new_user_code, 
            USERNAME=username,  
            USER_TYPE=role,
            IS_LOCKED_OUT=0
        )
        new_user.set_password(password)

        # Add the new user to the database
        db.session.add(new_user)
        db.session.commit()

        flash(f"User '{username}' created successfully with role '{role}' and code '{new_user_code}'.", "success")
        return redirect(url_for('administrator_bp.dashboard'))

    return render_template('administrator/add_user.html')

@administrator_bp.route('/locked_users', methods=['GET'])
def locked_users():
    locked_users = User.query.filter_by(IS_LOCKED_OUT=1).all()
    return render_template('administrator/locked_users.html', locked_users=locked_users)


@administrator_bp.route('/unlock/<int:user_id>', methods=['POST'])
def unlock(user_id):
    user = User.query.get_or_404(user_id)
    user.clear_failed_attempts()
    user.IS_LOCKED_OUT = 0
    db.session.commit()
    flash(f'Account for {user.USERNAME} has been unlocked.', 'success')
    return redirect(url_for('administrator_bp.locked_users'))



@administrator_bp.route('/unlock_all', methods=['POST'])
def unlock_all():
    locked_users = User.query.filter_by(IS_LOCKED_OUT=1).all()
    for user in locked_users:
        user.clear_failed_attempts()
        user.IS_LOCKED_OUT = 0
    db.session.commit()
    flash('All locked accounts have been unlocked.', 'success')
    return redirect(url_for('administrator_bp.locked_users'))
