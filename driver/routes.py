# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-.../driver/routes.py
# Import session from flask for your multi-sponsor logic
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from common.logging import DRIVER_POINTS
# Keep the combined imports
from models import Role, AuditLog, User, db, Sponsor, DriverApplication, Address, StoreSettings, Driver, DriverSponsorAssociation, CartItem, Purchase
from extensions import bcrypt

# Blueprint for driver-related routes
driver_bp = Blueprint('driver_bp', __name__, template_folder="../templates")

# Login - This route might be deprecated if login is fully handled by auth_bp.
# Keeping it for now, but ensure it doesn't conflict with auth_bp.login
# Using the simpler version from HEAD as the auth_bp handles more complex logic.
@driver_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(USERNAME=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            # Redirect to the multi-sponsor dashboard
            return redirect(url_for('driver_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    # Use the driver-specific login template if it exists, otherwise a common one
    return render_template('driver/login.html') # Assuming driver/login.html exists

# New dashboard to show all sponsors and point totals
@driver_bp.route('/dashboard')
@role_required(Role.DRIVER)
def dashboard():
    # Fetch associations for the multi-sponsor view
    associations = DriverSponsorAssociation.query.filter_by(driver_id=current_user.USER_CODE).all()
    # Add sponsor names to associations for display
    for assoc in associations:
        sponsor_user = User.query.get(assoc.sponsor_id)
        assoc.sponsor_name = f"{sponsor_user.FNAME} {sponsor_user.LNAME}" if sponsor_user else "Unknown Sponsor"
        sponsor_profile = Sponsor.query.get(assoc.sponsor_id) # Fetch Sponsor profile too
        assoc.org_name = sponsor_profile.ORG_NAME if sponsor_profile else "N/A" # Use Sponsor profile for ORG_NAME

    return render_template('driver/dashboard.html', user=current_user, associations=associations)

# New route to select a sponsor's store
@driver_bp.route('/select_store/<int:sponsor_id>')
@role_required(Role.DRIVER)
def select_store(sponsor_id):
    assoc = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    if not assoc:
        flash("You are not associated with this sponsor's store.", "danger")
        return redirect(url_for('driver_bp.dashboard'))

    # Store the selected sponsor's ID in the user's session
    session['current_sponsor_id'] = sponsor_id

    # Clear any old cart items from a different sponsor's store
    CartItem.query.filter(CartItem.user_id == current_user.USER_CODE, CartItem.sponsor_id != sponsor_id).delete()
    db.session.commit()

    # Redirect to the rewards store page
    return redirect(url_for('rewards_bp.store'))

# Point History
@driver_bp.route('/point_history')
@role_required(Role.DRIVER)
def point_history():
    # This query remains the same, but contextually might need sponsor filtering later
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS,
        AuditLog.DETAILS.like(f"%driver {current_user.USERNAME}%") # Make search slightly more specific
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("driver/point_history.html", events=events)

# Logout
@driver_bp.route('/logout')
@login_required
def logout():
    user_id = current_user.USER_CODE # Get ID before logout
    logout_user()
    # Clear session data, including current_sponsor_id
    session.clear()
    flash("You have been logged out.", "info")
    # Redirect to the main auth login route
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
    # Get the driver profile
    driver = Driver.query.get(current_user.USER_CODE)

    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        license_number = request.form.get('license_number')

        # Basic email validation
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))

        # Check if email already exists for another user
        if User.query.filter(User.EMAIL == email, User.USER_CODE != current_user.USER_CODE).first():
            flash('Email address already in use by another account.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))

        try:
            current_user.EMAIL = email
            current_user.PHONE = phone # Okay to store None if empty
            # Update license number only if it's a driver and number provided
            if driver and license_number:
                driver.LICENSE_NUMBER = license_number

            db.session.commit()
            flash('Contact information updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger') # Show specific error for debugging
            # Redirect back to the form on error
            return redirect(url_for('driver_bp.update_contact')) # Corrected redirect target

    return render_template('driver/update_info.html', user=current_user, driver=driver)

# Update Password
@driver_bp.route('/change_password', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verify current password
        if not current_user.PASS or not bcrypt.check_password_hash(current_user.PASS, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('driver_bp.change_password'))

        # Validate new password
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('driver_bp.change_password'))

        if len(new_password) < 8: # Keep basic length check
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('driver_bp.change_password'))

        # Update password using the set_password method
        try:
            current_user.set_password(new_password) # Use the model method
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating password: {e}', 'danger')
            return redirect(url_for('driver_bp.change_password'))

    # Render the change password template
    return render_template('driver/change_password.html')


# Driver Application to Sponsors
@driver_bp.route("/driver_app", methods=["GET", "POST"])
@login_required
@role_required(Role.DRIVER)
def apply_driver():
    # Fetch approved sponsors
    sponsors = Sponsor.query.filter_by(STATUS="Approved").all()
    # Add user info to sponsors for display
    for sponsor in sponsors:
        sponsor_user = User.query.get(sponsor.SPONSOR_ID)
        sponsor.display_name = f"{sponsor_user.FNAME} {sponsor_user.LNAME} ({sponsor.ORG_NAME})" if sponsor_user else sponsor.ORG_NAME


    if request.method == "POST":
        sponsor_id = request.form.get("sponsor_id", type=int)
        reason = request.form.get("reason", "")

        if not sponsor_id:
             flash("Invalid sponsor selected.", "danger")
             return redirect(url_for("driver_bp.apply_driver"))


        # Check if driver profile exists
        driver = Driver.query.get(current_user.USER_CODE)
        if not driver:
            flash("Could not find your driver profile. Please contact support.", "danger")
            return redirect(url_for("driver_bp.dashboard"))

        # Check for existing pending/accepted application or association
        existing_app = DriverApplication.query.filter_by(
            DRIVER_ID=current_user.USER_CODE,
            SPONSOR_ID=sponsor_id
        ).filter(DriverApplication.STATUS.in_(['Pending', 'Accepted'])).first()

        existing_assoc = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))


        if existing_assoc:
             flash("You are already associated with this sponsor.", "warning")
        elif existing_app:
            flash(f"You already have a {existing_app.STATUS.lower()} application with this sponsor.", "warning")
        else:
            # Create new application
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

    # GET request
    return render_template("driver/driver_app.html", sponsors=sponsors)

# --- Address Management ---

@driver_bp.route('/addresses')
@role_required(Role.DRIVER)
def addresses():
    # Query addresses for the current user to display them
    user_addresses = Address.query.filter_by(user_id=current_user.USER_CODE).order_by(Address.is_default.desc()).all()
    return render_template('driver/addresses.html', addresses=user_addresses)

@driver_bp.route('/addresses/add', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def add_address():
    if request.method == 'POST':
        is_default = request.form.get('is_default') == 'on'
        # If setting this as default, unset others first
        if is_default:
            Address.query.filter_by(user_id=current_user.USER_CODE, is_default=True).update({'is_default': False})

        new_address = Address(
            user_id=current_user.USER_CODE,
            street=request.form['street'],
            city=request.form['city'],
            state=request.form['state'],
            zip_code=request.form['zip_code'],
            is_default=is_default
        )
        db.session.add(new_address)
        db.session.commit()
        flash('Address added successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    # Pass action='add' to the template
    return render_template('driver/address_form.html', action='add')

@driver_bp.route('/addresses/edit/<int:address_id>', methods=['GET', 'POST'])
@role_required(Role.DRIVER)
def edit_address(address_id):
    address = Address.query.get_or_404(address_id)
    # Authorization check
    if address.user_id != current_user.USER_CODE:
        flash("You are not authorized to edit this address.", "danger")
        return redirect(url_for('driver_bp.addresses'))

    if request.method == 'POST':
        is_default = request.form.get('is_default') == 'on'
        # If setting this as default, unset others first
        if is_default:
             Address.query.filter_by(user_id=current_user.USER_CODE, is_default=True).update({'is_default': False})

        address.street = request.form['street']
        address.city = request.form['city']
        address.state = request.form['state']
        address.zip_code = request.form['zip_code']
        address.is_default = is_default
        db.session.commit()
        flash('Address updated successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    # Pass action='edit' and the address object
    return render_template('driver/address_form.html', address=address, action='edit')

@driver_bp.route('/addresses/delete/<int:address_id>', methods=['POST'])
@role_required(Role.DRIVER)
def delete_address(address_id):
    address = Address.query.get_or_404(address_id)
    # Authorization check
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
    # Authorization check
    if address.user_id != current_user.USER_CODE:
        flash("You are not authorized to modify this address.", "danger")
        return redirect(url_for('driver_bp.addresses'))

    # Unset existing default, then set new one
    Address.query.filter_by(user_id=current_user.USER_CODE, is_default=True).update({'is_default': False})
    address.is_default = True
    db.session.commit()
    flash('Default address has been updated!', 'success')
    return redirect(url_for('driver_bp.addresses'))

# View Purchase History (Keep version from 'main' which adds sponsor name)
@driver_bp.route('/purchase_history')
@role_required(Role.DRIVER)
def purchase_history():
    """Displays the driver's purchase history across all sponsors."""
    purchases = Purchase.query.filter_by(
        user_id=current_user.USER_CODE
    ).order_by(Purchase.purchase_date.desc()).all()

    # Add sponsor org name for display
    for purchase in purchases:
        sponsor = Sponsor.query.get(purchase.sponsor_id)
        purchase.sponsor_org_name = sponsor.ORG_NAME if sponsor else "N/A"

    return render_template('driver/purchase_history.html', purchases=purchases)