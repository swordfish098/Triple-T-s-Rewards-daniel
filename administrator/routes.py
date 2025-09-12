from flask import Blueprint, render_template

administrator_bp = Blueprint("administrator", __name__, template_folder="../templates")

@administrator_bp.get("/dashboard")
def dashboard():
    return render_template("administrator/dashboard.html")
