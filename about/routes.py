import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import AboutInfo, Role
from common.decorators import role_required
from forms import AboutForm

about_bp = Blueprint("about_bp", __name__, template_folder="../templates")

VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version_info.json')

@about_bp.get("/")
def view_about():
    info = AboutInfo.query.order_by(AboutInfo.entry_id.desc()).first()
    version_info = load_version_info()
    release_date = datetime.strptime(version_info["release_date"], "%Y-%m-%d")
    return render_template("about/dashboard.html", info=info, release_date=release_date, version_num=version_info["version"])

def load_version_info():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return json.load(f)
    return {"version": 1, "release_date": datetime.now().strftime("%Y-%m-%d")}

def save_version_info(info):
    with open(VERSION_FILE, 'w') as f:
        json.dump(info, f)

def should_update_version(last_release_date: datetime) -> bool:
    """Check if a week has passed since the last release"""
    if not last_release_date:
        return True
    time_since_release = datetime.now() - last_release_date
    return time_since_release >= timedelta(minutes=1)

def update_version():
    """Update version number and release date if a week has passed"""
    info = _get_singleton_about()
    
    if info is None:
        info = AboutInfo()
        info.team_num = 12
        info.product_name = "Team Twelve Trucking"
        info.product_desc = "Triple T Rewards Program"
        info.version_num = 1
        info.release_date = datetime.now()
    elif should_update_version(info.release_date):
        info.version_num += 1
        info.release_date = datetime.now()
    
    db.session.add(info)
    db.session.commit()

def _get_singleton_about() -> AboutInfo | None:
    return AboutInfo.query.order_by(AboutInfo.entry_id.desc()).first()

# Public view (everyone)
@about_bp.route('/about')
def about_page():
    about_info = AboutInfo.query.get(2)  # Get the last (or only) record
    return render_template('about/dashboard.html', about_info=about_info)


@about_bp.route("/administrator/about", methods=["GET", "POST"])
@role_required(Role.ADMINISTRATOR, allow_admin=False)
def edit_about():
    form = AboutForm()
    info = _get_singleton_about()

    if form.validate_on_submit():
        # Handle form submission
        if info is None:
            info = AboutInfo()
        info.team_num = form.team_num.data
        info.version_num = form.version_num.data
        info.product_name = form.product_name.data
        info.product_desc = form.product_desc.data
        db.session.add(info)
        db.session.commit()
        return redirect(url_for("about.about_page"))

    # Pre-fill form with existing data
    if info and request.method == 'GET':
        form.team_num.data = info.team_num
        form.version_num.data = info.version_num
        form.product_name.data = info.product_name
        form.product_desc.data = info.product_desc

    return render_template("about/edit_about.html", form=form, info=info)