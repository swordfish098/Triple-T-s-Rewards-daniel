# config.py
import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fdf3b077e67f77d9b75322212cd0d50f8932ed96db890458caaeab3aa27c2f44')
    # Make sure the database URI is correct for your setup
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://Team12:paSsword@cpsc4910-f25.cobd8enwsupz.us-east-1.rds.amazonaws.com/Team12_DB')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Keep the engine options from HEAD
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # Checks connection validity before use
        "pool_recycle": 3600    # Recycles connections after 1 hour (3600 seconds)
    }