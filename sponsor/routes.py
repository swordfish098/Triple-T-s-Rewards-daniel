from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from models import User, Role

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

# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)  
def dashboard():
    # Looks inside templates/sponsor/dashboard.html
    return render_template('sponsor/dashboard.html', user=current_user)

# Logout
@sponsor_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('sponsor_bp.login'))
