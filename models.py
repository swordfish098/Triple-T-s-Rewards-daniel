from datetime import datetime, timedelta
from extensions import db, login_manager
from flask_login import UserMixin
import bcrypt
import secrets
from english_words import english_words_set
import random
import string

LOCKOUT_ATTEMPTS = 3
WORDS = list(english_words_set)

class AuditLog(db.Model):
    __tablename__ = 'AUDIT_LOG'
    EVENT_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    EVENT_TYPE = db.Column(db.String(50), nullable=False)
    DETAILS = db.Column(db.Text, nullable=True)
    CREATED_AT = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    

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
    #User PI
    USER_CODE = db.Column(db.Integer, primary_key=True)
    USERNAME = db.Column(db.String(50), unique=True, nullable=False)
    PASS = db.Column(db.String(255), nullable=True)  
    USER_TYPE = db.Column(db.String(20), nullable=False)
    FNAME = db.Column(db.String(50), nullable=False)
    LNAME = db.Column(db.String(50), nullable=False)
    EMAIL = db.Column(db.String(100), nullable=False)
    CREATED_AT = db.Column(db.DateTime, nullable=False)
    POINTS = db.Column(db.Integer, default=0, nullable=False)

    #User account
    IS_ACTIVE = db.Column(db.Integer, nullable=False)
    FAILED_ATTEMPTS = db.Column(db.Integer, default=0, nullable=False)
    LOCKOUT_TIME = db.Column(db.DateTime, nullable=True)
    RESET_TOKEN = db.Column(db.String(255), nullable=True, index=True)
    RESET_TOKEN_CREATED_AT = db.Column(db.DateTime, nullable=True)
    IS_LOCKED_OUT = db.Column(db.Integer, nullable=False)
    
    def log_event(self, event_type: str, details: str = None):
        log_entry = AuditLog(EVENT_TYPE=event_type, DETAILS=details)
        db.session.add(log_entry)
        db.session.commit()

    def set_password(self):
        words = list(WORDS)
        word = random.choice(words)
        num_digits = 6
        numbers = ''.join(secrets.choice(string.digits) for _ in range(num_digits))
        password = word + numbers
        self.PASS = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        return password


    def check_password(self, password : str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.PASS.encode('utf-8'))
    
    def is_account_locked(self) -> bool:
        if self.LOCKOUT_TIME and datetime.utcnow() < self.LOCKOUT_TIME:
            self.IS_LOCKED_OUT = 1
            return True
        return False
    
    def register_failed_attempt(self):
        self.FAILED_ATTEMPTS += 1
        if self.FAILED_ATTEMPTS >= LOCKOUT_ATTEMPTS:
            self.LOCKOUT_TIME = datetime.utcnow() + timedelta(minutes=15)
            self.IS_LOCKED_OUT = 1

    def clear_failed_attempts(self):
        self.FAILED_ATTEMPTS = 0
        self.LOCKOUT_TIME = None
        self.IS_LOCKED_OUT = 0

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

class CartItem(db.Model):
    __tablename__ = 'CART_ITEMS'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE'), nullable=False)
    item_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
