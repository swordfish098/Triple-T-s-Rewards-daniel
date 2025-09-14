import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fdf3b077e67f77d9b75322212cd0d50f8932ed96db890458caaeab3aa27c2f44')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://root:astrok120@localhost/tripletdb')
    SQLALCHEMY_TRACK_MODIFICATIONS = False