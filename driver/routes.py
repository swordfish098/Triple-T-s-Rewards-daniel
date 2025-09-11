from flask import Blueprint, render_template

driver_bp = Blueprint('driver', __name__, template_folder="../templates")

@driver_bp.get('/dashboard')
def dashboard():
    return render_template('driver/dashboard.html')