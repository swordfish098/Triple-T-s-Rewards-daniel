# models.py
from datetime import datetime, timedelta
from extensions import db, login_manager # Keep combined
from extensions import bcrypt # Keep combined
import secrets
from english_words import english_words_set
import random
import string
from flask_login import UserMixin
# --- Merged Imports ---
from sqlalchemy.orm import relationship # Keep relationship for associations
import pyotp # Add pyotp for 2FA
# itsdangerous is not used directly in the merged model, can be removed if not used elsewhere
from itsdangerous import URLSafeTimedSerializer

# Constants
LOCKOUT_ATTEMPTS = 3
WORDS = list(english_words_set)

# --- Model Definitions ---

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
    # Use default=datetime.utcnow for consistency
    release_date = db.Column(db.DateTime, default=datetime.utcnow)
    product_name = db.Column(db.String(255))
    product_desc = db.Column(db.Text)

class User(db.Model, UserMixin):
    __tablename__ = 'USERS'
    # --- Combined Columns ---
    USER_CODE = db.Column(db.Integer, primary_key=True)
    USERNAME = db.Column(db.String(50), unique=True, nullable=False)
    PASS = db.Column(db.String(255), nullable=True) # Hashed password
    USER_TYPE = db.Column(db.String(20), nullable=False) # 'driver', 'sponsor', 'administrator'
    FNAME = db.Column(db.String(50), nullable=False)
    LNAME = db.Column(db.String(50), nullable=False)
    EMAIL = db.Column(db.String(100), nullable=False, unique=True) # Added unique constraint
    CREATED_AT = db.Column(db.DateTime, default=datetime.utcnow, nullable=False) # Added default
    # Removed POINTS column - Points are now tracked per sponsor in DriverSponsorAssociation
    PHONE = db.Column(db.String(15), nullable=True)
    # Notification preferences (consistent)
    wants_point_notifications = db.Column(db.Boolean, default=True, nullable=False)
    wants_order_notifications = db.Column(db.Boolean, default=True, nullable=False)
    # 2FA fields (from 078d...)
    TOTP_SECRET = db.Column(db.String(32), nullable=True) # Increased length for safety
    TOTP_ENABLED = db.Column(db.Boolean, default=False, nullable=False)
    # Account status fields (combined)
    IS_ACTIVE = db.Column(db.Integer, default=1, nullable=False) # Default to active (1)
    FAILED_ATTEMPTS = db.Column(db.Integer, default=0, nullable=False)
    LOCKOUT_TIME = db.Column(db.DateTime, nullable=True)
    # Use the longer String length for LOCKED_REASON from 078d...
    LOCKED_REASON = db.Column(db.String(255), nullable=True) # e.g., 'failed_attempts', 'admin'
    # Use Integer for IS_LOCKED_OUT (0 or 1)
    IS_LOCKED_OUT = db.Column(db.Integer, default=0, nullable=False) # Default to not locked (0)
    # Password reset fields (consistent)
    RESET_TOKEN = db.Column(db.String(255), nullable=True, index=True)
    RESET_TOKEN_CREATED_AT = db.Column(db.DateTime, nullable=True)

    # --- Relationships (combined) ---
    addresses = db.relationship('Address', backref='user', lazy=True, cascade="all, delete-orphan")
    wishlist_items = db.relationship('WishlistItem', backref='user', lazy=True, cascade="all, delete-orphan")
    # Add backrefs for notifications if needed, consistent between versions
    notifications_sent = db.relationship('Notification', foreign_keys='Notification.SENDER_CODE', backref='sender', lazy='dynamic')
    notifications_received = db.relationship('Notification', foreign_keys='Notification.RECIPIENT_CODE', backref='recipient', lazy='dynamic')
    # Add backref for purchases if needed (from HEAD)
    purchases = db.relationship('Purchase', backref='user', lazy='dynamic')


    # --- Methods (combined) ---
    def log_event(self, event_type: str, details: str = None):
        """Logs an audit event related to this user."""
        # Include USER_CODE/USERNAME in details automatically?
        log_entry = AuditLog(EVENT_TYPE=event_type, DETAILS=details)
        db.session.add(log_entry)
        # Consider committing audit logs separately or let the caller handle commits
        # db.session.commit()

    def set_password(self, password: str) -> None:
        """Hashes and sets the user's password."""
        if not password:
             raise ValueError("Password cannot be empty")
        self.PASS = bcrypt.generate_password_hash(password).decode("utf-8")

    def admin_set_new_pass(self) -> str:
        """Generates a random password (word + numbers), hashes it, sets it, and returns the plain password."""
        if not WORDS: # Basic check in case english_words fails
            word = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
        else:
            word = random.choice(WORDS)
        num_digits = 6
        numbers = ''.join(secrets.choice(string.digits) for _ in range(num_digits))
        password = word + numbers

        # Use the correct bcrypt method from HEAD's fix
        self.PASS = bcrypt.generate_password_hash(password).decode('utf-8')
        return password

    def check_password(self, password : str) -> bool:
        """Checks if the provided password matches the stored hash."""
        if not self.PASS or not password:
            return False
        return bcrypt.check_password_hash(self.PASS, password)

    def is_account_locked(self) -> bool:
        """Checks if the account is currently locked out by time."""
        if self.IS_LOCKED_OUT == 1 and self.LOCKOUT_TIME and datetime.utcnow() < self.LOCKOUT_TIME:
            return True
        # If lockout time has passed, automatically unlock (unless locked by admin without time?)
        # Consider adding logic here to clear IS_LOCKED_OUT if time expired, except for 'admin' reason?
        # For now, just return based on current flag and time.
        # Check IS_LOCKED_OUT flag directly too, in case of admin lock without time
        if self.IS_LOCKED_OUT == 1 and self.LOCKED_REASON == 'admin' and not self.LOCKOUT_TIME:
            return True # Indefinite admin lock
        return False


    # --- 2FA Methods (from 078d...) ---
    def get_totp_uri(self):
        """Generates the URI for QR code generation."""
        # Ensure TOTP_SECRET exists before generating URI
        if not self.TOTP_SECRET:
             self.TOTP_SECRET = pyotp.random_base32()
             # Note: Need to commit this change in the route calling this if it's generated here.
        return f'otpauth://totp/TripleTRewards:{self.USERNAME}?secret={self.TOTP_SECRET}&issuer=TripleTRewards'

    def get_totp(self):
        """Returns a pyotp.TOTP object for verification."""
        if not self.TOTP_SECRET:
            return None
        return pyotp.TOTP(self.TOTP_SECRET)

    # --- Account Lockout/Reset Methods (combined/consistent) ---
    def register_failed_attempt(self):
        """Increments failed attempts and locks account if threshold reached."""
        if self.IS_LOCKED_OUT == 1: # Don't increment if already locked
             return
        self.FAILED_ATTEMPTS += 1
        if self.FAILED_ATTEMPTS >= LOCKOUT_ATTEMPTS:
            self.LOCKOUT_TIME = datetime.utcnow() + timedelta(minutes=15) # Standard lockout duration
            self.IS_LOCKED_OUT = 1
            self.LOCKED_REASON = "failed_attempts"
            # Log this event?

    def clear_failed_attempts(self):
        """Resets failed attempts count and unlocks the account if locked by attempts."""
        self.FAILED_ATTEMPTS = 0
        # Only clear lockout if it was due to failed attempts
        if self.LOCKED_REASON == "failed_attempts":
            self.LOCKOUT_TIME = None
            self.IS_LOCKED_OUT = 0
            self.LOCKED_REASON = None

    def generate_reset_token(self) -> str:
        """Generates a secure password reset token."""
        token = secrets.token_urlsafe(48)
        self.RESET_TOKEN = token
        self.RESET_TOKEN_CREATED_AT = datetime.utcnow()
        return token

    def clear_reset_token(self):
        """Clears the password reset token fields."""
        self.RESET_TOKEN = None
        self.RESET_TOKEN_CREATED_AT = None

    # Flask-Login required method
    def get_id(self):
        """Returns the user's ID (USER_CODE) as a string."""
        return str(self.USER_CODE)

# --- Role-Specific Profile Models (consistent) ---

class Driver(db.Model):
    __tablename__ = 'DRIVERS'
    # Define primary key explicitly referencing USERS table
    DRIVER_ID = db.Column(db.Integer, db.ForeignKey("USERS.USER_CODE", ondelete="CASCADE"), primary_key=True)
    LICENSE_NUMBER = db.Column(db.String(50), nullable=True) # Allow null? Or default?
    # Relationship back to User (optional but can be useful)
    user = db.relationship("User", backref=db.backref("driver_profile", uselist=False))
    # Relationship to applications (consistent)
    applications = db.relationship("DriverApplication", back_populates="driver", cascade="all, delete-orphan")
    # Relationship to associations (from HEAD)
    sponsor_associations = db.relationship("DriverSponsorAssociation", back_populates="driver", cascade="all, delete-orphan")


class Sponsor(db.Model):
    __tablename__ = "SPONSORS"
    SPONSOR_ID = db.Column(db.Integer, db.ForeignKey("USERS.USER_CODE", ondelete="CASCADE"), primary_key=True)
    ORG_NAME = db.Column(db.String(100), nullable=False)
    # Use Enum directly
    STATUS = db.Column(db.Enum("Pending", "Approved", "Rejected", name="SPONSOR_STATUS"), default="Pending", nullable=False)
    # Relationship back to User (optional)
    user = db.relationship("User", backref=db.backref("sponsor_profile", uselist=False))
    # Relationship to applications (consistent)
    applications = db.relationship("DriverApplication", back_populates="sponsor", cascade="all, delete-orphan")
    # Relationship to associations (from HEAD)
    driver_associations = db.relationship("DriverSponsorAssociation", back_populates="sponsor", cascade="all, delete-orphan")
    # Relationship to store settings (from HEAD)
    store_settings = db.relationship("StoreSettings", back_populates="sponsor", uselist=False, cascade="all, delete-orphan")

class Admin(db.Model):
    __tablename__ = "ADMIN"
    ADMIN_ID = db.Column(db.Integer, db.ForeignKey("USERS.USER_CODE", ondelete="CASCADE"), primary_key=True)
    ROLE_TITLE = db.Column(db.String(100), nullable=True) # Allow null?
    # Relationship back to User (optional)
    user = db.relationship("User", backref=db.backref("admin_profile", uselist=False))


# --- Association and Application Models ---

# DriverSponsorAssociation (from HEAD - CRITICAL for multi-sponsor)
class DriverSponsorAssociation(db.Model):
    __tablename__ = 'DRIVER_SPONSOR_ASSOCIATIONS'
    # Composite primary key
    driver_id = db.Column(db.Integer, db.ForeignKey('DRIVERS.DRIVER_ID', ondelete="CASCADE"), primary_key=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('SPONSORS.SPONSOR_ID', ondelete="CASCADE"), primary_key=True)
    # Points specific to this relationship
    points = db.Column(db.Integer, default=0, nullable=False)

    # Define relationships with back_populates for clarity
    driver = db.relationship("Driver", back_populates="sponsor_associations")
    sponsor = db.relationship("Sponsor", back_populates="driver_associations")


class DriverApplication(db.Model):
    __tablename__ = "DRIVER_APPLICATIONS"
    APPLICATION_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Foreign keys referencing profile tables
    DRIVER_ID = db.Column(db.Integer, db.ForeignKey("DRIVERS.DRIVER_ID", ondelete="CASCADE"), nullable=False)
    SPONSOR_ID = db.Column(db.Integer, db.ForeignKey("SPONSORS.SPONSOR_ID", ondelete="CASCADE"), nullable=False)
    STATUS = db.Column(db.Enum("Pending", "Accepted", "Rejected", name="DRIVER_APPLICATION_STATUS"), default="Pending", nullable=False)
    REASON = db.Column(db.String(255), nullable=True) # Reason for application or rejection
    # Use default=datetime.utcnow for consistency
    APPLIED_AT = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships (consistent, use back_populates)
    driver = db.relationship("Driver", back_populates="applications")
    sponsor = db.relationship("Sponsor", back_populates="applications")

# --- Store and Item Models ---

# StoreSettings (Use HEAD version - sponsor-specific)
class StoreSettings(db.Model):
    __tablename__ = 'STORE_SETTINGS'
    id = db.Column(db.Integer, primary_key=True)
    # Link settings directly to a Sponsor
    sponsor_id = db.Column(db.Integer, db.ForeignKey('SPONSORS.SPONSOR_ID', ondelete="CASCADE"), nullable=False, unique=True)
    ebay_category_id = db.Column(db.String(50), nullable=False, default='2984')
    point_ratio = db.Column(db.Integer, nullable=False, default=10) # CHECK: Should this be Float?

    # Relationship (use back_populates)
    sponsor = db.relationship("Sponsor", back_populates="store_settings")

# CartItem (Use HEAD version - sponsor-specific)
class CartItem(db.Model):
    __tablename__ = 'CART_ITEMS'
    id = db.Column(db.Integer, primary_key=True)
    # Link to User
    user_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE', ondelete="CASCADE"), nullable=False)
    # Link to Sponsor - identifies which sponsor's cart this is in
    sponsor_id = db.Column(db.Integer, db.ForeignKey('SPONSORS.SPONSOR_ID', ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.String(255), nullable=False) # eBay item ID
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    # Relationship back to user (consistent) - consider removing backref string if using explicit relationship on User
    # user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    user = db.relationship('User', backref='cart_items') # Simpler backref
    # Optional relationship to Sponsor if needed
    sponsor = db.relationship('Sponsor') # No backref needed if not navigating Sponsor->CartItem

    # Add unique constraint? A user shouldn't have the same item_id twice for the same sponsor.
    __table_args__ = (db.UniqueConstraint('user_id', 'sponsor_id', 'item_id', name='uq_user_sponsor_item'),)


# Notification (Consistent between versions)
class Notification(db.Model):
    __tablename__ = 'NOTIFICATIONS'
    NOTIFICATION_ID = db.Column(db.Integer, primary_key=True)
    SENDER_CODE = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE'), nullable=False)
    RECIPIENT_CODE = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE'), nullable=False)
    TIMESTAMP = db.Column(db.DateTime, default=datetime.utcnow, nullable=False) # Add default
    MESSAGE = db.Column(db.Text, nullable=False)
    # Use Boolean for READ_STATUS for clarity
    READ_STATUS = db.Column(db.Boolean, default=False, nullable=False) # Default to unread

    # Relationships defined on User model using foreign_keys argument

    @staticmethod
    def create_notification(recipient_code, sender_code, message):
        """Creates and commits a new notification."""
        if not recipient_code or not sender_code or not message:
             # Add basic validation or logging
             print("Attempted to create notification with missing data.")
             return None

        notification = Notification(
            RECIPIENT_CODE=recipient_code,
            SENDER_CODE=sender_code,
            # TIMESTAMP defaults to utcnow
            MESSAGE=message,
            # READ_STATUS defaults to False
        )
        db.session.add(notification)
        try:
            # Let the caller handle commit unless specifically needed here
            # db.session.commit()
            db.session.flush() # Flush to get potential errors without full commit
        except Exception as e:
            db.session.rollback()
            print(f"Error creating notification: {e}") # Log error
            raise e # Re-raise for caller to handle
        return notification

# Purchase (from HEAD - CRITICAL for multi-sponsor checkout)
class Purchase(db.Model):
    __tablename__ = 'PURCHASES'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE', ondelete="CASCADE"), nullable=False)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('SPONSORS.SPONSOR_ID', ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.String(255), nullable=False) # eBay item ID
    title = db.Column(db.String(255), nullable=False)
    points = db.Column(db.Integer, nullable=False) # Points spent at time of purchase
    quantity = db.Column(db.Integer, nullable=False, default=1)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships - backref defined on User model
    # user = db.relationship('User', backref=db.backref('purchases', lazy=True))
    sponsor = db.relationship('Sponsor') # Optional relationship to Sponsor


# Address (Consistent)
class Address(db.Model):
    __tablename__ = 'ADDRESSES'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE', ondelete="CASCADE"), nullable=False) # Added cascade delete
    street = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    # Relationship defined on User model

# WishlistItem (Consistent, added unique constraint check)
class WishlistItem(db.Model):
    __tablename__ = 'WISHLIST_ITEMS'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE', ondelete="CASCADE"), nullable=False) # Added cascade delete
    # Make item_id unique per user, not globally
    item_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False) # Price at time of adding?
    points = db.Column(db.Integer, nullable=False) # Points equivalent at time of adding?
    image_url = db.Column(db.String(255), nullable=True)

    # Relationship defined on User model

    # Add unique constraint for user_id and item_id
    __table_args__ = (db.UniqueConstraint('user_id', 'item_id', name='uq_user_wishlist_item'),)


# ImpersonationLog (from 078d... - CRITICAL for impersonation)
class ImpersonationLog(db.Model):
    __tablename__ = 'IMPERSONATION_LOG'
    id = db.Column(db.Integer, primary_key=True)
    # Actor is the user performing the impersonation (e.g., admin)
    actor_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE'), nullable=False)
    # Target is the user being impersonated
    target_id = db.Column(db.Integer, db.ForeignKey('USERS.USER_CODE'), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # 'start' or 'stop'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Optional relationships to User for easier querying
    actor = db.relationship('User', foreign_keys=[actor_id], backref='impersonations_performed')
    target = db.relationship('User', foreign_keys=[target_id], backref='impersonations_received')