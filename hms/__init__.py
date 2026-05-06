import os
import pyodbc
from flask import Flask, render_template
from flask_login import LoginManager
from config import get_db_connection_params, config


class Database:
    """Simple database wrapper using pyodbc instead of SQLAlchemy."""
    
    def __init__(self):
        self.connection_params = None
    
    def init_app(self, app):
        """Initialize database with app configuration."""
        self.connection_params = app.config.get('DB_CONNECTION_PARAMS', {})
    
    def get_connection(self):
        """Get a new database connection."""
        if not self.connection_params:
            raise RuntimeError("Database not initialized. Call init_app first.")
        
        driver = self.connection_params['driver']
        server = self.connection_params['server']
        database = self.connection_params['database']
        username = self.connection_params.get('username')
        password = self.connection_params.get('password')
        
        conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        
        if username and password:
            conn_str += f"UID={username};PWD={password};"
        else:
            conn_str += "Trusted_Connection=yes;"
        
        return pyodbc.connect(conn_str)


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
