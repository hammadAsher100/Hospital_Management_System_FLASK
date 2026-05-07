import os
import pyodbc
from flask import Flask, render_template
from flask_login import LoginManager
from config import get_db_connection_params, config

# ── Design Pattern: Singleton ────────────────────────────────────────────────
# DatabaseSingleton is imported here (before the Database wrapper is defined)
# so that get_connection() can delegate to it.  The actual singleton instance
# is created lazily inside Database.init_app() once connection params are known.
from hms.patterns.singleton import DatabaseSingleton


class Database:
    """
    Database wrapper using pyodbc instead of SQLAlchemy.

    **Singleton Pattern** — ``get_connection()`` delegates to
    ``DatabaseSingleton`` so the whole application shares a single
    ``pyodbc`` connection instance rather than opening a new one on
    every call.  The singleton is initialised lazily in ``init_app()``
    once the connection parameters are available.
    """

    def __init__(self):
        self.connection_params = None

    def init_app(self, app):
        """Initialise database with app configuration and prime the Singleton."""
        self.connection_params = app.config.get('DB_CONNECTION_PARAMS', {})
        # Prime the Singleton instance so the first request doesn't pay the
        # connection-open cost.  Safe to call multiple times — only one
        # instance is ever created.
        if self.connection_params and self.connection_params.get('driver'):
            try:
                DatabaseSingleton.get_instance(self.connection_params)
            except Exception as exc:
                print(f"[Database.init_app] Singleton priming deferred: {exc}")

    def get_connection(self):
        """
        Return the shared database connection via the Singleton.

        The Singleton transparently reconnects if the connection has
        been closed or lost, so callers never need to handle that.
        """
        if not self.connection_params:
            raise RuntimeError("Database not initialized. Call init_app first.")

        # ── Singleton Pattern ────────────────────────────────────────────
        # Obtain (or create) the singleton and return its shared connection.
        singleton = DatabaseSingleton.get_instance(self.connection_params)
        return singleton.get_connection()


db = Database()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


def _ensure_tables_for_sqlite(app):
    """Serverless SQLite (e.g. Vercel fallback) has no schema until tables exist."""
    uri = (app.config.get('DATABASE_URI') or '').strip().lower()
    if not uri.startswith('sqlite'):
        return
    print('[HMS] Using SQLite - ensure schema.sql has been run')


def create_app(config_name=None):
    if config_name is None:
        if os.environ.get('VERCEL') or os.environ.get('FLASK_ENV') == 'production':
            config_name = 'production'
        else:
            config_name = 'default'
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Get database connection parameters
    db_params = get_db_connection_params()
    app.config['DB_CONNECTION_PARAMS'] = db_params
    app.config['DATABASE_URI'] = db_params.get('uri', '')

    db.init_app(app)
    login_manager.init_app(app)

    # Import database operations module
    from hms import db_operations
    from hms.models.user import User

    _ensure_tables_for_sqlite(app)
    if os.environ.get('VERCEL'):
        db_uri = app.config.get('DATABASE_URI') or ''
        preview = db_uri.split('@')[-1] if '@' in db_uri else db_uri
        print(f'[HMS] Effective database (host/path): {preview}')

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    # Context processor — makes 'now' and 'today' available in every template
    from datetime import datetime, date as date_type

    @app.context_processor
    def inject_globals():
        from hms.models.pharmacy import Medicine
        low_stock_count = 0
        try:
            low_stock_meds = Medicine.get_low_stock()
            low_stock_count = len(low_stock_meds)
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

    # Optional startup DB check
    if not os.environ.get('VERCEL'):
        with app.app_context():
            try:
                conn = db.get_connection()
                conn.close()
                print("[OK] Database connection successful.")
            except Exception as e:
                print(f"[WARNING] Database connection failed: {e}")
                print("   Make sure SSMS is running and .env is configured correctly.")

    return app
