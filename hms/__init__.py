import os

try:
    from flask import Flask, render_template
    from flask_login import LoginManager
except Exception:  # pragma: no cover
    Flask = None
    render_template = None
    LoginManager = None

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover
    psycopg2 = None


class Database:
    """
    Lightweight database wrapper using psycopg2.

    Replaces the previous pyodbc/Singleton implementation.
    Each call to get_connection() returns a fresh psycopg2 connection;
    callers are responsible for closing it (all db_operations functions do this).
    """

    def __init__(self):
        self._database_url = None

    def init_app(self, app):
        """Initialise with the app's DATABASE URL."""
        self._database_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        # Smoke-test the connection at startup (non-fatal)
        if not os.environ.get('TESTING'):
            try:
                conn = self.get_connection()
                conn.close()
                print("[OK] PostgreSQL connection successful.")
            except Exception as exc:
                print(f"[WARNING] Database connection failed: {exc}")

    def get_connection(self):
        """Return a new psycopg2 connection."""
        if psycopg2 is None:
            raise RuntimeError(
                "psycopg2 is not installed. Add psycopg2-binary to requirements.txt."
            )
        if not self._database_url:
            raise RuntimeError("Database not initialised. Call init_app() first.")

        conn = psycopg2.connect(self._database_url)
        conn.autocommit = False
        return conn


db = Database()

if LoginManager is not None:
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
else:  # pragma: no cover
    login_manager = None


def create_app(config_name=None):
    if Flask is None:
        raise RuntimeError(
            "Flask is not installed. Install dependencies from requirements.txt."
        )

    from config import config

    if config_name is None:
        env = os.environ.get('FLASK_ENV', '')
        config_name = 'production' if env == 'production' else 'default'

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)

    if login_manager is None:
        raise RuntimeError(
            "Flask-Login is not installed. Install dependencies from requirements.txt."
        )
    login_manager.init_app(app)

    from hms.models.user import User

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

    return app
