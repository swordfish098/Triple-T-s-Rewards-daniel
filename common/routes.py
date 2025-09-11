from flask import Blueprint, render_template

common_bp = Blueprint('common', __name__, template_folder="../templates")

@common_bp.get('/')
def index():
    return render_template('common/index.html')