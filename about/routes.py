import os
import json
from datetime import datetime
from flask import Blueprint, render_template

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
    info["version"] += 1
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
