import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import AboutInfo, Role
from common.decorators import role_required


about_bp = Blueprint("about", __name__, template_folder="../templates")

VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version_info.json')

def load_version_info():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return json.load(f)
    return {"version": 1, "release_date": datetime.now().strftime("%Y-%m-%d")}

def save_version_info(info):
    with open(VERSION_FILE, 'w') as f:
        json.dump(info, f)

def update_version():
    """Update version number and release date"""
    info = load_version_info()
    info["version"] = info.get("version", 0) + 1
    info["release_date"] = datetime.now().strftime("%Y-%m-%d")
    save_version_info(info)

@about_bp.get("/dashboard")
def dashboard():
    version_info = load_version_info()
    return render_template(
        "about/dashboard.html",
        version_num=version_info["version"],
        release_date=datetime.strptime(version_info["release_date"], "%Y-%m-%d")
    )

def _get_singleton_about() -> AboutInfo | None:
    return AboutInfo.query.order_by(AboutInfo.entry_id.desc()).first()

# Public view (everyone)
@about_bp.get("/about")
def view_about():
    info = _get_singleton_about()
    return render_template("common/about.html", info=info)


@about_bp.route("/administrator/about", methods=["GET", "POST"])
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def edit_about():
    info = _get_singleton_about()

    if request.method == "POST":
        # If CSRFProtect is enabled, {{ csrf_token() }} in the template will validate this POST
        product_name = request.form.get("product_name", "").strip()
        product_desc = request.form.get("product_desc", "").strip()
        team_num     = request.form.get("team_num", "").strip()
        version_num  = request.form.get("version_num", "").strip()
        release_date = datetime.utcnow()  # stamp save time

        if not info:
            info = AboutInfo()

        # basic assignments (coerce ints where possible)
        info.product_name = product_name or None
        info.product_desc = product_desc or None
        info.team_num     = int(team_num) if team_num.isdigit() else None
        info.version_num  = int(version_num) if version_num.isdigit() else None
        info.release_date = release_date

        db.session.add(info)
        db.session.commit()
        
        update_version()
        
        flash("About page saved.", "success")
        return redirect(url_for("about.edit_about"))

    # GET
    version = load_version_info()
    if info:
        info.version_num = version.get("version", 1)
        info.release_date = datetime.strptime(version.get("release_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
    else:
        info = AboutInfo(
            product_name="",
            product_desc="",
            team_num=None,
            version_num=version.get("version", 1),
            release_date=datetime.strptime(version.get("release_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
        )
    return render_template("about/dashboard.html", info=info, version=version["version"], release_date=info.release_date)