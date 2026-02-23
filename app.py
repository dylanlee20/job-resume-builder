"""
NewWhale Career v2 - Application Factory
AI-Proof Industries Job Tracker with Resume Assessment
"""
from flask import Flask, request as flask_request, redirect, url_for, flash
from flask_login import LoginManager, current_user, logout_user
from flask_wtf.csrf import CSRFProtect
from models.database import db, init_db
from models.user import User, create_admin_user
from config import Config
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO if not Config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Ensure required directories exist
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(Config.EXCEL_EXPORT_PATH), exist_ok=True)
    os.makedirs(Config.UPLOAD_FOLDER_RESUMES, exist_ok=True)
    os.makedirs(Config.UPLOAD_FOLDER_TEMPLATES, exist_ok=True)
    os.makedirs(os.path.dirname(Config.LOG_PATH), exist_ok=True)
    
    # Initialize database
    init_db(app)
    
    # Initialize CSRF protection
    csrf = CSRFProtect(app)
    logger.info("CSRF protection enabled")
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create default admin account
    with app.app_context():
        create_admin_user(
            username=Config.ADMIN_USERNAME,
            password=Config.ADMIN_PASSWORD,
            email='admin@newwhale.com'
        )
    
    # Register blueprints (import here to avoid circular imports)
    from routes.auth import auth_bp
    from routes.web import web_bp
    from routes.api import api_bp
    from routes.admin import admin_bp
    from routes.resume_routes import resume_bp
    from routes.payment_routes import payment_bp, stripe_webhook
    from routes.outreach_routes import outreach_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(outreach_bp)

    # Exempt endpoints from CSRF
    csrf.exempt(stripe_webhook)
    from routes.outreach_routes import track_open
    csrf.exempt(track_open)

    # Import models so they're registered with SQLAlchemy
    from models.cold_email import EmailCampaign, EmailRecipient
    
    # Initialize job scheduler
    from scheduler.job_scheduler import JobScheduler
    scheduler = JobScheduler(app)
    
    # Only start scheduler if not disabled
    if os.environ.get('DISABLE_SCHEDULER', 'false').lower() != 'true':
        try:
            scheduler.start()
            logger.info("Job scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start job scheduler: {e}")
    else:
        logger.info("Scheduler disabled (set DISABLE_SCHEDULER=false to enable)")
    
    # Add cleanup on shutdown
    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        try:
            scheduler.stop()
        except:
            pass
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        db.session.rollback()
        return {'error': 'Internal server error'}, 500
    
    # File upload error handler
    @app.errorhandler(413)
    def file_too_large(error):
        return {
            'error': f'File too large. Maximum size is {Config.UPLOAD_MAX_SIZE_MB}MB'
        }, 413
    
    logger.info("Flask application created successfully")
    
    return app, scheduler


if __name__ == '__main__':
    # Create application
    app, scheduler = create_app()
    
    # Run application
    logger.info(f"Starting Flask application on {Config.HOST}:{Config.PORT}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Database: {Config.DATABASE_PATH}")
    logger.info(f"Excel export path: {Config.EXCEL_EXPORT_PATH}")
    logger.info(f"Resume uploads: {Config.UPLOAD_FOLDER_RESUMES}")
    
    try:
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG,
            use_reloader=False  # Disable auto-reload to avoid scheduler duplication
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Shutting down application...")
