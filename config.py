"""
Configuration module for NewWhale Career v2
Loads all settings from environment variables for security
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.absolute()


class Config:
    """Application configuration from environment variables"""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set!")
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR}/data/jobs.db')
    DATABASE_PATH = str(BASE_DIR / 'data' / 'jobs.db')
    
    # Flask
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 5000)))
    
    # Admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    if not ADMIN_PASSWORD:
        raise ValueError("ADMIN_PASSWORD environment variable must be set!")
    
    # Stripe Payment
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID_MONTHLY = os.environ.get('STRIPE_PRICE_ID_MONTHLY')
    STRIPE_PRICE_ID_ANNUAL = os.environ.get('STRIPE_PRICE_ID_ANNUAL')
    
    # LLM API
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    
    # File Upload
    UPLOAD_MAX_SIZE_MB = int(os.environ.get('UPLOAD_MAX_SIZE_MB', 10))
    MAX_CONTENT_LENGTH = UPLOAD_MAX_SIZE_MB * 1024 * 1024  # Convert to bytes
    ALLOWED_RESUME_EXTENSIONS = os.environ.get(
        'ALLOWED_RESUME_EXTENSIONS', 'pdf,docx'
    ).split(',')
    
    UPLOAD_FOLDER_RESUMES = str(BASE_DIR / 'uploads' / 'resumes')
    UPLOAD_FOLDER_TEMPLATES = str(BASE_DIR / 'uploads' / 'templates')
    
    # Rate Limiting
    FREE_TIER_DAILY_ASSESSMENTS = int(
        os.environ.get('FREE_TIER_DAILY_ASSESSMENTS', 3)
    )
    
    # Paths
    EXCEL_EXPORT_PATH = str(BASE_DIR / 'data' / 'exports' / 'jobs_export.xlsx')
    LOG_PATH = str(BASE_DIR / 'data' / 'logs' / 'app.log')
    
    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
