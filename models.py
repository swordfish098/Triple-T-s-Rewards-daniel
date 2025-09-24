from datetime import datetime, timedelta
from extensions import db, login_manager
from flask_login import UserMixin
import bcrypt
import secrets

LOCKOUT_ATTEMPTS = 3

class Role:
    DRIVER = 'driver'
    SPONSOR = 'sponsor'
    ADMINISTRATOR = 'administrator'
    
    @staticmethod
    def choices():
        return [Role.DRIVER, Role.SPONSOR, Role.ADMINISTRATOR]

class AboutInfo(db.Model):
    __tablename__ = 'ABOUT_INFO'
    entry_id = db.Column(db.Integer, primary_key=True)
    team_num = db.Column(db.Integer)
    version_num = db.Column(db.Integer)
    release_date = db.Column(db.DateTime, default=datetime.utcnow)
    product_name = db.Column(db.String(255))
    product_desc = db.Column(db.Text)
    
class User(db.Model, UserMixin):
    __tablename__ = 'USERS'
    USER_CODE = db.Column(db.Integer, primary_key=True)
    USERNAME = db.Column(db.String(50), unique=True, nullable=False)
    PASS = db.Column(db.String(255), nullable=True)  
    USER_TYPE = db.Column(db.String(20), nullable=False)

    FAILED_ATTEMPTS = db.Column(db.Integer, default=0, nullable=False)
    LOCKOUT_TIME = db.Column(db.DateTime, nullable=True)
    RESET_TOKEN = db.Column(db.String(255), nullable=True, index=True)
    RESET_TOKEN_CREATED_AT = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str):
        self.PASS = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password : str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.PASS.encode('utf-8'))
    
    def is_account_locked(self) -> bool:
        if self.LOCKOUT_TIME and datetime.utcnow() < self.LOCKOUT_TIME:
            return True
        return False
    
    def register_failed_attempt(self):
        self.FAILED_ATTEMPTS += 1
        if self.FAILED_ATTEMPTS >= LOCKOUT_ATTEMPTS:
            self.LOCKOUT_TIME = datetime.utcnow() + timedelta(minutes=15)

    def clear_failed_attempts(self):
        self.FAILED_ATTEMPTS = 0
        self.LOCKOUT_TIME = None

    def generate_reset_token(self) -> str:
        token = secrets.token_urlsafe(48)
        self.RESET_TOKEN = token
        self.RESET_TOKEN_CREATED_AT = datetime.utcnow()
        return token
    
    def clear_reset_token(self):
        self.RESET_TOKEN = None
        self.RESET_TOKEN_CREATED_AT = None
        
    def get_id(self):
        return str(self.USER_CODE)

    
class StoreSettings(db.Model):
    __tablename__ = 'STORE_SETTINGS'
    id = db.Column(db.Integer, primary_key=True)
    ebay_category_id = db.Column(db.String(50), nullable=False, default='2984')
    point_ratio = db.Column(db.Integer, nullable=False, default=10)
