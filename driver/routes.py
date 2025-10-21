# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-72ca7a46f1915a7f669f3692e9b77d23b248eaee/driver/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from common.logging import DRIVER_POINTS
from models import Role, AuditLog, User, db, Sponsor, DriverApplication, Address, StoreSettings, Driver, DriverSponsorAssociation, CartItem, Purchase
from extensions import bcrypt

# Blueprint for driver-related routes
driver_bp = Blueprint('driver_bp', __name__, template_folder="../templates")

# Login
@driver_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(USERNAME=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('driver_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    return render_template('driver/login.html')

# New dashboard to show all sponsors and point totals
@driver_bp.route('/dashboard')
@role_required(Role.DRIVER)
def dashboard():
    associations = DriverSponsorAssociation.query.filter_by(driver_id=current_user.USER_CODE).all()
    return render_template('driver/dashboard.html', user=current_user, associations=associations)

# New route to select a sponsor's store
@driver_bp.route('/select_store/<int:sponsor_id>')
@role_required(Role.DRIVER)
def select_store(sponsor_id):
    assoc = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    if not assoc:
        flash("You are not authorized to view this store.", "danger")
        return redirect(url_for('driver_bp.dashboard'))

    # Store the selected sponsor's ID in the user's session
    session['current_sponsor_id'] = sponsor_id
    
    # Clear any old cart items from a different sponsor's store
    CartItem.query.filter(CartItem.user_id == current_user.USER_CODE, CartItem.sponsor_id != sponsor_id).delete()
    db.session.commit()

    return redirect(url_for('rewards_bp.store'))

# Point History (This might need to be adjusted later to show history per sponsor)
@driver_bp.route('/point_history')
@role_required(Role.DRIVER)
def point_history():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS,
        AuditLog.DETAILS.like(f"%{current_user.USERNAME}%")
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("driver/point_history.html", events=events)

# Logout
@driver_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear() # Clear session data, including current_sponsor_id
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

# Settings Page
@driver_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def settings():
    if request.method == 'POST':
        wants_points = request.form.get('wants_point_notifications') == 'on'
        wants_orders = request.form.get('wants_order_notifications') == 'on'
        
        current_user.wants_point_notifications = wants_points
        current_user.wants_order_notifications = wants_orders
        db.session.commit()
        
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('driver_bp.dashboard'))
        
    return render_template('driver/settings.html')

# Update Contact Information
@driver_bp.route('/update_info', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def update_contact():
    driver = Driver.query.get(current_user.USER_CODE)

    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        license_number = request.form.get('license_number')

        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
            
        if User.query.filter(User.EMAIL == email, User.USER_CODE != current_user.USER_CODE).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
        
        try:
            current_user.EMAIL = email
            current_user.PHONE = phone
            if driver and license_number:
                driver.LICENSE_NUMBER = license_number

            db.session.commit()
            flash('Contact information updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your information', 'danger')
            return redirect(url_for('driver_bp.update_info'))
        
    return render_template('driver/update_info.html', user=current_user, driver=driver)

# Update Password
@driver_bp.route('/change_password', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not bcrypt.check_password_hash(current_user.PASS, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('driver_bp.change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
        try:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your password', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
    return render_template('driver/change_password.html')

# Driver Application
@driver_bp.route("/driver_app", methods=["GET", "POST"])
@login_required
def apply_driver():
    sponsors = Sponsor.query.filter_by(STATUS="Approved").all()

    if request.method == "POST":
        sponsor_id = request.form["sponsor_id"]
        reason = request.form.get("reason", "")

        existing = DriverApplication.query.filter_by(
            DRIVER_ID=current_user.USER_CODE,
            SPONSOR_ID=sponsor_id
        ).first()

        if existing:
            flash("You have already applied to this sponsor.", "warning")
        else:
            driver = Driver.query.get(current_user.USER_CODE)
            if not driver:
                flash("Could not find your driver profile. Please contact support.", "danger")
                return redirect(url_for("driver_bp.dashboard"))

            application = DriverApplication(
                DRIVER_ID=current_user.USER_CODE,
                SPONSOR_ID=sponsor_id,
                REASON=reason,
                STATUS="Pending"
            )
            db.session.add(application)
            db.session.commit()
            flash("Application submitted successfully! Await sponsor review.", "success")

        return redirect(url_for("driver_bp.dashboard"))

    return render_template("driver/driver_app.html", sponsors=sponsors)

# Address Management
@driver_bp.route('/addresses')
@role_required(Role.DRIVER)
def addresses():
    return render_template('driver/addresses.html')

@driver_bp.route('/addresses/add', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def add_address():
    if request.method == 'POST':
        new_address = Address(
            user_id=current_user.USER_CODE,
            street=request.form['street'],
            city=request.form['city'],
            state=request.form['state'],
            zip_code=request.form['zip_code'],
            is_default=request.form.get('is_default') == 'on'
        )
        db.session.add(new_address)
        db.session.commit()
        flash('Address added successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    return render_template('driver/address_form.html')

@driver_bp.route('/addresses/edit/<int:address_id>', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def edit_address(address_id):
    address = Address.query.get_or_404(address_id)
    if address.user_id != current_user.USER_CODE:
        flash("You are not authorized to edit this address.", "danger")
        return redirect(url_for('driver_bp.addresses'))

    if request.method == 'POST':
        address.street = request.form['street']
        address.city = request.form['city']
        address.state = request.form['state']
        address.zip_code = request.form['zip_code']
        address.is_default = request.form.get('is_default') == 'on'
        db.session.commit()
        flash('Address updated successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    return render_template('driver/address_form.html', address=address)

@driver_bp.route('/addresses/delete/<int:address_id>', methods=['POST'])
@role_required(Role.DRIVER)
def delete_address(address_id):
    address = Address.query.get_or_404(address_id)
    if address.user_id != current_user.USER_CODE:
        flash("You are not authorized to delete this address.", "danger")
        return redirect(url_for('driver_bp.addresses'))

    db.session.delete(address)
    db.session.commit()
    flash('Address deleted successfully!', 'success')
    return redirect(url_for('driver_bp.addresses'))

@driver_bp.route('/addresses/set_default/<int:address_id>', methods=['POST'])
@role_required(Role.DRIVER)
def set_default_address(address_id):
    address = Address.query.get_or_404(address_id)
    if address.user_id != current_user.USER_CODE:
        flash("You are not authorized to modify this address.", "danger")
        return redirect(url_for('driver_bp.addresses'))
        
    Address.query.filter_by(user_id=current_user.USER_CODE, is_default=True).update({'is_default': False})
    address.is_default = True
    db.session.commit()
    flash('Default address has been updated!', 'success')
    return redirect(url_for('driver_bp.addresses'))

# View Purchase History
@driver_bp.route('/purchase_history')
@role_required(Role.DRIVER)
def purchase_history():
    """Displays the driver's purchase history across all sponsors."""
    
    # 1. Query the Purchase table, filtering by the current driver's ID
    purchases = Purchase.query.filter_by(
        user_id=current_user.USER_CODE
    ).order_by(Purchase.purchase_date.desc()).all()

    # 2. Render the template with the list of purchases
    # Assumes templates/driver/purchase_history.html exists
    return render_template('driver/purchase_history.html', purchases=purchases)