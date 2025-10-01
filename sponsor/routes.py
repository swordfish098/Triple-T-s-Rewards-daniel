from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from models import User, Role, StoreSettings
from extensions import db
from models import db, DriverApplication
from datetime import datetime # <-- Import datetime


# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)
        db.session.commit()
    drivers = User.query.filter_by(USER_TYPE=Role.DRIVER).all()
    return render_template('sponsor/dashboard.html', settings=settings, drivers=drivers)

# Update Store Settings
@sponsor_bp.route('/update_settings', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)
    settings.ebay_category_id = request.form.get('ebay_category_id')
    settings.point_ratio = int(request.form.get('point_ratio'))
    db.session.commit()
    flash("Store settings updated successfully!", "success")
    return redirect(url_for('sponsor_bp.dashboard'))

# Award Points to a Driver
@sponsor_bp.route('/award_points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def award_points(driver_id):
    driver = User.query.get_or_404(driver_id)
    points_to_add = request.form.get('points', type=int)

    if driver and points_to_add is not None:
        driver.POINTS += points_to_add
        db.session.commit()
        flash(f"Successfully awarded {points_to_add} points to {driver.USERNAME}.", "success")
    else:
        flash("Could not award points. Please try again.", "danger")

    return redirect(url_for('sponsor_bp.dashboard'))

# Add a New Driver
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')

        existing_user = User.query.filter(
            (User.USERNAME == username) | (User.EMAIL == email)
        ).first()
        if existing_user:
            flash(f"Username or email already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))

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

    return render_template('sponsor/add_user.html')
