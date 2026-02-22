"""Application configuration"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.absolute()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production-please')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    TESTING = False

    DATABASE_PATH = str(BASE_DIR / 'data' / 'newwhale.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR}/data/newwhale.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'NewWhale2024!')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@newwhaletech.com')

    UPLOAD_FOLDER = str(BASE_DIR / 'uploads' / 'resumes')
    TEMPLATE_FOLDER_UPLOAD = str(BASE_DIR / 'uploads' / 'templates')
    MAX_CONTENT_LENGTH = int(os.environ.get('UPLOAD_MAX_MB', 10)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}

    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
