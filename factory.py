"""Application factory for NewWhale Career v2"""
import os
import logging
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from extensions import db, migrate, login_manager, csrf
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s'
    )

    for directory in [
        app.config['UPLOAD_FOLDER'],
        app.config['TEMPLATE_FOLDER_UPLOAD'],
        os.path.dirname(app.config.get('DATABASE_PATH', 'data/app.db')),
    ]:
        os.makedirs(directory, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    with app.app_context():
        from models.user import User
        from models.job import Job
        from models.resume import Resume
        from models.assessment import ResumeAssessment
        from models.subscription import Subscription, Payment
        from models.scraper_run import ScraperRun

        db.create_all()
        _create_admin(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.jobs import jobs_bp
    from routes.resume import resume_bp
    from routes.payment import payment_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def file_too_large(e):
        return render_template('errors/413.html'), 413

    return app


def _create_admin(app):
    from models.user import User
    admin_username = app.config.get('ADMIN_USERNAME', 'admin')
    admin_password = app.config.get('ADMIN_PASSWORD')
    if not admin_password:
        return
    existing = User.query.filter_by(username=admin_username).first()
    if not existing:
        admin = User(
            username=admin_username,
            email=app.config.get('ADMIN_EMAIL', 'admin@newwhaletech.com'),
            is_admin=True,
            tier='premium'
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        logging.getLogger(__name__).info(f'Admin user created: {admin_username}')
