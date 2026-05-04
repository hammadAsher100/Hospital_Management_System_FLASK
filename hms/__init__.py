import os

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import _sqlalchemy_database_uri, config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


def _ensure_tables_for_sqlite(app):
    """Serverless SQLite (e.g. Vercel fallback) has no schema until tables exist."""
    uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').strip().lower()
    if not uri.startswith('sqlite'):
        return
    with app.app_context():
        db.create_all()
        db.session.commit()


def create_app(config_name=None):
    if config_name is None:
        if os.environ.get('VERCEL') or os.environ.get('FLASK_ENV') == 'production':
            config_name = 'production'
        else:
            config_name = 'default'
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # Re-resolve DB URI at app init (not only at config import) so Vercel env is visible
    # and we never keep a stale mssql+pyodbc URL from an earlier import context.
    app.config['SQLALCHEMY_DATABASE_URI'] = _sqlalchemy_database_uri()

    db.init_app(app)
    login_manager.init_app(app)

    from hms.models.user import User
    # Import all models so SQLAlchemy can discover them
    from hms.models import patient, doctor, appointment, billing, pharmacy, admission  # noqa

    _ensure_tables_for_sqlite(app)
    if os.environ.get('VERCEL'):
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        preview = db_uri.split('@')[-1] if '@' in db_uri else db_uri
        print(f'[HMS] Effective database (host/path): {preview}')

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Context processor — makes 'now' and 'today' available in every template
    from datetime import datetime, date as date_type

    @app.context_processor
    def inject_globals():
        from hms.models.pharmacy import Medicine
        low_stock_count = 0
        try:
            low_stock_count = Medicine.query.filter(
                Medicine.stock_quantity <= Medicine.reorder_level
            ).count()
        except Exception:
            pass
        return {
            'now': datetime.utcnow(),
            'today': date_type.today(),
            'global_low_stock': low_stock_count,
        }

    # Register blueprints
    from hms.routes.auth import auth_bp
    from hms.routes.patients import patients_bp
    from hms.routes.appointments import appointments_bp
    from hms.routes.staff import staff_bp
    from hms.routes.billing import billing_bp
    from hms.routes.pharmacy import pharmacy_bp
    from hms.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(patients_bp, url_prefix='/patients')
    app.register_blueprint(appointments_bp, url_prefix='/appointments')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Root redirect
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.is_patient():
                return redirect(url_for('patients.patient_dashboard'))
            if current_user.is_doctor():
                return redirect(url_for('staff.doctor_dashboard'))
            if current_user.is_nurse():
                return redirect(url_for('staff.nurse_dashboard'))
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('auth.login'))

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception('500: %s', e)
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    # Optional startup DB check (skipped on Vercel: pyodbc/dialect init can fail hard in serverless)
    if not os.environ.get('VERCEL'):
        with app.app_context():
            try:
                db.engine.connect()
                print("[OK] Database connection successful.")
            except Exception as e:
                print(f"[WARNING] Database connection failed: {e}")
                print("   Make sure SSMS is running and .env is configured correctly.")

    return app
