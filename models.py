from datetime import datetime
from extensions import db, login_manager
from flask_login import UserMixin
import bcrypt

class Role:
    DRIVER = 'driver'
    SPONSOR = 'sponsor'
    ADMIN = 'admin'
    @staticmethod
    
    def choices():
        return [Role.DRIVER, Role.SPONSOR, Role.ADMIN]
    
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
    PASS = db.Column(db.String(255), nullable=False)  
    USER_TYPE = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.PASS = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.PASS.encode('utf-8'))
    
    def get_id(self):
        return str(self.USER_CODE)