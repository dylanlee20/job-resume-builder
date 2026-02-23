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
    
    # Email / SMTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp-mail.outlook.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no_reply_newwhale@outlook.com')
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')

    # Email verification token expiry in hours
    EMAIL_VERIFICATION_EXPIRY_HOURS = int(os.environ.get('EMAIL_VERIFICATION_EXPIRY_HOURS', 24))

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

    # Scraper Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = str(BASE_DIR / 'data' / 'logs' / 'scraper.log')
    HEADLESS_MODE = os.environ.get('HEADLESS_MODE', 'True').lower() == 'true'
    SCRAPER_TIMEOUT = int(os.environ.get('SCRAPER_TIMEOUT', 60))
    SCRAPER_DELAY_MIN = float(os.environ.get('SCRAPER_DELAY_MIN', 1.0))
    SCRAPER_DELAY_MAX = float(os.environ.get('SCRAPER_DELAY_MAX', 3.0))
    SCRAPER_RETRY_COUNT = int(os.environ.get('SCRAPER_RETRY_COUNT', 3))

    # Chrome/Chromium binary path (auto-detected if not set)
    CHROME_BINARY_PATH = os.environ.get('CHROME_BINARY_PATH', '')
