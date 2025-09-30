from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from models import Role 
from models import User
from models import db, Sponsor, DriverApplication

# Blueprint for driver-related routes
driver_bp = Blueprint('driver_bp', __name__, template_folder="../templates")

# Login
@driver_bp.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('driver_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    # Looks inside templates/driver/login.html
    return render_template('driver/login.html')

# Dashboard
@driver_bp.route('/dashboard')
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def dashboard():
    # Looks inside templates/driver/dashboard.html
    return render_template('driver/dashboard.html', user=current_user)

# Logout
@driver_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

# Update Account Information
@driver_bp.route('/update_info', methods=['GET', 'POST'])
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def update_info():
    from extensions import db
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Basic email validation
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('driver_bp.update_info'))
            
        # Check if email already exists for another user
        if User.query.filter(User.EMAIL == email, User.USER_CODE != current_user.USER_CODE).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('driver_bp.update_info'))
            
        try:
            current_user.EMAIL = email
            db.session.commit()
            flash('Email updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your email.', 'danger')
            return redirect(url_for('driver_bp.update_info'))

    # Prefill form with current user info
    return render_template('driver/update_info.html', user=current_user)

driver_bp = Blueprint("driver_bp", __name__, template_folder="../templates/driver")

# Driver Application
@driver_bp.route("/apply", methods=["GET", "POST"])
@login_required
def apply_driver():
    sponsors = Sponsor.query.filter_by(STATUS="Approved").all()
    if request.method == "POST":
        sponsor_id = request.form["sponsor_id"]

        # check for duplicates
        existing = DriverApplication.query.filter_by(DRIVER_ID=current_user.USER_CODE, SPONSOR_ID=sponsor_id).first()
        if existing:
            flash("You already applied to this sponsor.", "warning")
        else:
            application = DriverApplication(DRIVER_ID=current_user.USER_CODE, SPONSOR_ID=sponsor_id)
            db.session.add(application)
            db.session.commit()
            flash("Application submitted successfully!", "success")

        return redirect(url_for("driver_bp.dashboard"))

    return render_template("apply_driver.html", sponsors=sponsors)
