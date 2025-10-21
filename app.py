# app.py
from datetime import datetime
import os
# --- Merged Imports ---
# Added session and g for impersonation
from flask import Flask, redirect, render_template, request, url_for, flash, session, g
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from flask_login import current_user, logout_user
from extensions import db, migrate, login_manager, csrf, bcrypt
from config import Config
from models import User
from flask_wtf.csrf import CSRFProtect
# Removed redundant imports of extensions

# Initialize scheduler and CSRF protection
scheduler = APScheduler()
# csrf object is imported from extensions, no need to redefine here

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    # Kept SECRET_KEY and WTF_CSRF_TIME_LIMIT from upstream for completeness
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["WTF_CSRF_TIME_LIMIT"] = None  # Disable time limit on CSRF tokens

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Central login view
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    bcrypt.init_app(app)

    # Custom error handler
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('common/403.html'), 403

    # --- Register Blueprints ---
    # Import all blueprints from both versions
    from driver.routes import driver_bp
    from auth.routes import auth_bp
    from administrator.routes import administrator_bp
    from sponsor.routes import sponsor_bp
    from truck_rewards.routes import rewards_bp
    from common.routes import common_bp
    from about.routes import about_bp, update_version
    from notifications.routes import notification_bp
    # Import the impersonation blueprint from upstream
    from impersonation.routes import impersonation_bp

    # Register all blueprints, using prefixes from upstream where specified
    app.register_blueprint(about_bp, url_prefix='/about')
    # Use the /auth prefix from upstream for better organization
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(driver_bp, url_prefix='/driver')
    app.register_blueprint(administrator_bp, url_prefix='/administrator')
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(rewards_bp, url_prefix='/truck-rewards')
    app.register_blueprint(common_bp) # No prefix for common routes like index
    app.register_blueprint(notification_bp, url_prefix='/notifications')
    # Register the new impersonation blueprint
    app.register_blueprint(impersonation_bp, url_prefix='/impersonation')

    # Schedule the version update job
    with app.app_context():
        update_version()

    # Configure scheduler to check periodically
    scheduler.add_job(
        id='check_version',
        func=lambda: update_version(app=app), # Pass app context to scheduled job
        trigger='interval',
        hours=24  # Check once per day
    )
    # Uncomment to start the scheduler if needed
    # if not scheduler.running:
    #    scheduler.start()

    return app

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None

# Unauthorized handler
@login_manager.unauthorized_handler
def unauth():
    flash("You must be logged in to view that page.", "info")
    return redirect(url_for("auth.login"))

# Create the Flask app instance
app = create_app()

# --- Before Request Handlers ---

@app.before_request
def before_request_handler():
    """
    Combines multiple before_request checks into one function for clarity.
    This function runs before every request.
    """
    # 1. Skip checks for static files to improve performance
    if request.endpoint and 'static' in request.endpoint:
        return

    # 2. Enforce lockouts for authenticated users (from HEAD)
    if current_user.is_authenticated and current_user.is_account_locked():
        # Capture username for logging before logout
        locked_user = current_user.USERNAME
        logout_user()
        flash(f"Account '{locked_user}' is locked. Please contact an administrator.", "danger")
        return redirect(url_for("auth.login"))

    # 3. Load impersonation state into the global 'g' object (from 078d...)
    g.is_impersonating = bool(session.get('impersonating'))
    g.impersonator = None
    if g.is_impersonating and session.get('original_user_code'):
        impersonator_code = session.get('original_user_code')
        # Use a safe query to get the impersonator object
        g.impersonator = User.query.filter_by(USER_CODE=impersonator_code).first()


# --- Main Application Execution ---

if __name__ == '__main__':
    app.run(debug=True)