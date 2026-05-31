from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from hms import db_operations
from hms.models.user import User

# ── Design Pattern: Factory ────────────────────────────────────────────────
# UserRoleFactory creates a role-specific wrapper object (AdminUser, DoctorUser,
# PatientUser, NurseUser, BillingUser) that encapsulates permissions and the
# correct dashboard URL for each role.
from hms.patterns.factory import UserRoleFactory

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        user_module = request.form.get('user_module', 'staff')

        user = User.get_by_username(username)

        if user and user.check_password(password) and user.is_active:
            # Validate that user is trying to access the correct module
            # For doctors: allow both 'doctor' and 'staff' module access
            # For patients: allow only 'patient' module access
            # For other staff: allow only 'staff' module access
            if user.is_doctor() and user_module in ['doctor', 'staff']:
                access_allowed = True
            elif user.is_patient() and user_module == 'patient':
                access_allowed = True
            elif user.is_staff() and user_module == 'staff':
                access_allowed = True
            else:
                access_allowed = False
            
            if not access_allowed:
                flash('You do not have access to this module.', 'danger')
                return render_template('auth/login.html')
            
            # Defensive check: doctor-role users MUST have a doctors profile row.
            # Without it, the doctor dashboard will fail with "profile not found".
            if user.is_doctor():
                doctor_profile = db_operations.get_doctor_by_user_id(user.user_id)
                if not doctor_profile:
                    flash('Your doctor profile is not set up. Please contact an administrator.', 'danger')
                    return render_template('auth/login.html')

            login_user(user, remember=bool(remember))
            user.update_last_login()
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            # Redirect based on role
            return redirect_based_on_role(user)
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Patient sign-up route"""
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        
        # Validation
        if not all([username, email, password, first_name, last_name, phone, dob, gender]):
            flash('All fields are required.', 'danger')
            return render_template('auth/signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/signup.html')
        
        try:
            dob_value = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date of birth.', 'danger')
            return render_template('auth/signup.html')

        if dob_value > date.today():
            flash('Date of birth cannot be in the future.', 'danger')
            return render_template('auth/signup.html')

        try:
            # Pre-check uniques to return accurate messages (avoid relying on DB error strings).
            if db_operations.get_user_by_username(username):
                flash('Username already exists.', 'danger')
                return render_template('auth/signup.html')
            if db_operations.get_user_by_email(email):
                flash('Email already exists.', 'danger')
                return render_template('auth/signup.html')

            # Create user account
            user = User(
                user_id=0,  # Will be set by database
                username=username,
                email=email,
                password_hash='',  # Will be set below
                full_name=f"{first_name} {last_name}",
                role='patient'
            )
            user.set_password(password)
            
            # Insert user into database
            user_id = db_operations.create_user(
                username=username,
                password_hash=user.password_hash,
                role='patient',
                email=email,
                full_name=f"{first_name} {last_name}"
            )
            
            if not user_id:
                flash('Error creating user account.', 'danger')
                return render_template('auth/signup.html')
            
            # Create patient profile
            patient_id = db_operations.create_patient(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                dob=dob_value,
                gender=gender
            )
            
            if not patient_id:
                # Clean up orphan user to allow re-signup
                db_operations.execute_update(
                    "DELETE FROM users WHERE user_id = %s", (user_id,)
                )
                flash('Error creating patient profile.', 'danger')
                return render_template('auth/signup.html')
            
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'danger')
            return render_template('auth/signup.html')
    
    return render_template('auth/signup.html')


def validate_module_access(user, module):
    """Validate if user can access the selected module.
    
    Access rules:
    - Doctors: can access 'doctor' OR 'staff' module
    - Patients: can access only 'patient' module
    - Other staff (nurses, billing, admin): can access only 'staff' module
    """
    if user.is_doctor():
        # Doctors have special access to both doctor and staff modules
        return module in ['doctor', 'staff']
    elif user.is_patient():
        return module == 'patient'
    elif user.is_staff():
        return module == 'staff'
    return False


def redirect_based_on_role(user):
    """
    Redirect user to the appropriate dashboard based on their role.

    **Factory Pattern** — delegates dashboard-URL resolution to a
    role-specific ``RoleUser`` object produced by ``UserRoleFactory``
    instead of a hard-coded if/elif chain.
    """
    try:
        role_user = UserRoleFactory.create(user)
        dashboard_url = role_user.get_dashboard_url()
        print(
            f"[Factory] Created {role_user.__class__.__name__} for "
            f"'{user.username}' → {dashboard_url}"
        )
        return redirect(dashboard_url)
    except (ValueError, Exception) as exc:
        # Fallback: unknown role → send to login
        print(f"[Factory] Could not resolve role '{getattr(user, 'role', '?')}': {exc}")
        return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.is_patient():
        return redirect(url_for('patients.patient_profile'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', current_user.full_name).strip()
        email = request.form.get('email', current_user.email).strip()
        updated = db_operations.update_user_profile(
            user_id=current_user.user_id,
            full_name=full_name,
            email=email,
        )
        if updated:
            current_user.full_name = full_name
            current_user.email = email
            flash('Profile updated successfully.', 'success')
        else:
            flash('Unable to update profile right now.', 'danger')
    return render_template('auth/profile.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pass = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        confirm_pass = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pass):
            flash('Current password is incorrect.', 'danger')
        elif new_pass != confirm_pass:
            flash('New passwords do not match.', 'danger')
        elif len(new_pass) < 6:
            flash('Password must be at least 6 characters.', 'danger')
        else:
            current_user.set_password(new_pass)
            updated = db_operations.update_user_password_hash(
                user_id=current_user.user_id,
                password_hash=current_user.password_hash,
            )
            if updated:
                flash('Password changed successfully.', 'success')
            else:
                flash('Unable to change password right now.', 'danger')

    return render_template('auth/change_password.html')
