import os
from flask import Flask, render_template
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from extensions import db, migrate, login_manager, csrf
from config import Config
from models import User
from flask_wtf.csrf import CSRFProtect
from forms import AboutForm

# Initialize scheduler
scheduler = APScheduler()
csrf = CSRFProtect()

def create_app():
    # Load environment variables from .env file
    load_dotenv()


    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('common/403.html'), 403

    # Register blueprints
    from driver.routes import driver_bp
    from auth.routes import auth_bp
    from administrator.routes import administrator_bp
    from sponsor.routes import sponsor_bp
    from truck_rewards.routes import rewards_bp
    from common.routes import common_bp
    from about.routes import about_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(driver_bp, url_prefix='/driver')
    app.register_blueprint(administrator_bp, url_prefix='/administrator')
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(rewards_bp, url_prefix='/truck-rewards')
    app.register_blueprint(about_bp, url_prefix='/about')
    app.register_blueprint(common_bp)
    return app

@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))

app = create_app()

# Configure the scheduler
scheduler.api_enabled = True
scheduler.init_app(app)

# Add job to update version every Tuesday at midnight
#scheduler.add_job(id='update_version',
##                 trigger='cron',
#                 day_of_week='tue',
#                 hour=0,
#                 minute=0)

# Start the scheduler
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True)