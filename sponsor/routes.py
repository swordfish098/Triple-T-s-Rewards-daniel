from flask import Blueprint, render_template

sponsor_bp = Blueprint('sponsor', __name__, template_folder="../templates")

@sponsor_bp.get('/dashboard')
def dashboard():
    return render_template('sponsor/dashboard.html')