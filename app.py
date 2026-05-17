"""
NewWhale Career v2 - Application Factory
AI-Proof Industries Job Tracker with Resume Assessment
"""
from flask import Flask, request as flask_request, redirect, url_for, flash, jsonify, render_template
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
    os.makedirs(os.path.dirname(Config.LOG_PATH), exist_ok=True)

    # Import surviving models BEFORE init_db so create_all() sees every table
    from models.email_verification_token import EmailVerificationToken  # noqa: F401

    # Initialize database
    init_db(app)

    # Idempotent in-place migration: add users.status column if it's missing.
    # The deployed SQLite was created before admin freeze/disable existed.
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            insp = inspect(db.engine)
            cols = {c['name'] for c in insp.get_columns('users')} if 'users' in insp.get_table_names() else set()
            if cols and 'status' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'active' NOT NULL"))
                logger.info("Migrated: added users.status column.")
            if cols and 'allowed_apps' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN allowed_apps VARCHAR(100) DEFAULT '' NOT NULL"))
                logger.info("Migrated: added users.allowed_apps column.")
        except Exception as exc:
            logger.warning(f"Status-column migration skipped: {exc}")
    
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
    from routes.slides import slides_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(slides_bp)

    # Old /slides/* URLs (from prior deploys / cached pages) -> new /curriculum/*
    @app.route('/slides/', defaults={'rest': ''})
    @app.route('/slides/<path:rest>')
    def _slides_legacy_redirect(rest):
        return redirect('/curriculum/' + rest, code=301)

    # ------------------------------------------------------------------
    # Account-status gate: block frozen / disabled accounts
    # ------------------------------------------------------------------
    @app.before_request
    def enforce_account_status():
        if not current_user.is_authenticated:
            return
        if current_user.is_admin or current_user.is_active_account:
            return
        # Frozen or disabled — log them out and bounce to login.
        if flask_request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Account inactive', 'status': current_user.status}), 403
        status = current_user.status
        logout_user()
        msg = ('Your account has been frozen. Contact an admin to reactivate.'
               if status == 'frozen'
               else 'Your account has been disabled.')
        flash(msg, 'warning')
        return redirect(url_for('auth.login'))
    
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
        if flask_request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Not found'}), 404
        # Render a real 404 — no flash (it persists across redirects and
        # showed up as a permanent pink banner whenever a stale URL like
        # /resume/hub or /pricing came in from a cached page).
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        db.session.rollback()
        if flask_request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Internal server error'}), 500
        flash('Something went wrong. Please try again.', 'error')
        return redirect(url_for('web.dashboard'))

    # File upload error handler
    @app.errorhandler(413)
    def file_too_large(error):
        if flask_request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': f'File too large. Maximum size is {Config.UPLOAD_MAX_SIZE_MB}MB'}), 413
        flash(f'File too large. Maximum size is {Config.UPLOAD_MAX_SIZE_MB}MB.', 'error')
        return redirect(flask_request.referrer or url_for('web.dashboard'))
    
    logger.info("Flask application created successfully")
    
    return app, scheduler


# Module-level app for gunicorn
app, _scheduler = create_app()

if __name__ == '__main__':
    scheduler = _scheduler
    
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
