from flask import Blueprint, render_template
from models import AboutInfo

about_bp = Blueprint("about", __name__, template_folder="../templates")

@about_bp.get("/dashboard")
def dashboard():
    about_info = AboutInfo.query.get(1)  # 1 is the EntryID
    return render_template("about/dashboard.html", about_info=about_info)
    
