from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from models import User, Role, StoreSettings  
from extensions import db  
from models import User, Role
from extensions import db

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

# Login
@sponsor_bp.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('sponsor_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    # Looks inside templates/sponsor/login.html
    return render_template('sponsor/login.html')

# Logout
@sponsor_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    # Get the current store settings (or create them if they don't exist)
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
  
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'driver'

        existing_user = User.query.filter_by(USERNAME=username).first()
        if existing_user:
            flash("Username already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))
        
        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            new_user_code = 1
        
        new_user = User(
            USER_CODE=new_user_code,
            USERNAME=username,
            USER_TYPE=role
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash(f"User '{username}' created successfully!", "success")
        return redirect(url_for('sponsor_bp.dashboard'))
    
    return render_template('sponsor/add_user.html')
