from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User

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
@login_required
def dashboard():
    # Looks inside templates/driver/dashboard.html
    return render_template('driver/dashboard.html', user=current_user)

# Logout
@driver_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('driver_bp.login'))
