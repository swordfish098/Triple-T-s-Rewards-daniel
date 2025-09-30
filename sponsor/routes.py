from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from models import User, Role, StoreSettings
from extensions import db
from models import db, DriverApplication

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
    return render_template('sponsor/dashboard.html', settings=settings)

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

# Add a New Driver
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')

        existing_user = User.query.filter_by(USERNAME=username).first()
        if existing_user:
            flash(f"Username '{username}' already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))

        # Create the new user with the 'driver' role
        new_driver = User(USERNAME=username, 
                          EMAIL=email, 
                          USER_TYPE=Role.DRIVER)
        new_driver.set_password()
        
        db.session.add(new_driver)
        db.session.commit()
        
        flash(f"Driver '{username}' has been created successfully!", "success")
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