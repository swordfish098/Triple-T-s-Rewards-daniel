from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from common.decorators import role_required
from models import Role, StoreSettings
from extensions import db

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

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
        # This is a fallback, the dashboard should have already created it
        settings = StoreSettings()
        db.session.add(settings)

    settings.ebay_category_id = request.form.get('ebay_category_id')
    settings.point_ratio = int(request.form.get('point_ratio'))
    
    db.session.commit()
    
    flash("Store settings updated successfully!", "success")
    return redirect(url_for('sponsor_bp.dashboard'))