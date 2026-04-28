from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.patient import Patient
from datetime import datetime, date

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

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            # Validate that user is trying to access the correct module
            if not validate_module_access(user, user_module):
                flash('You do not have access to this module.', 'danger')
                return render_template('auth/login.html')
            
            login_user(user, remember=bool(remember))
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            # Redirect based on role
            return redirect_based_on_role(user)
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


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
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/signup.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
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
            # Create user account
            user = User(
                username=username,
                email=email,
                full_name=f"{first_name} {last_name}",
                role='patient'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            
            # Create patient profile
            patient = Patient(
                user_id=user.user_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                dob=dob_value,
                gender=gender
            )
            db.session.add(patient)
            db.session.commit()
            
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
            return render_template('auth/signup.html')
    
    return render_template('auth/signup.html')


def validate_module_access(user, module):
    """Validate if user can access the selected module"""
    if module == 'patient':
        return user.is_patient()
    elif module == 'doctor':
        return user.is_doctor()
    elif module == 'staff':
        return user.is_staff()
    return False


def redirect_based_on_role(user):
    """Redirect user to appropriate dashboard based on their role"""
    if user.is_patient():
        return redirect(url_for('patients.patient_dashboard'))
    elif user.is_doctor():
        return redirect(url_for('staff.doctor_dashboard'))
    elif user.is_nurse():
        return redirect(url_for('staff.nurse_dashboard'))
    else:  # admin or billing - both go to admin dashboard
        return redirect(url_for('admin.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.email = request.form.get('email', current_user.email)
        db.session.commit()
        flash('Profile updated successfully.', 'success')
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
            db.session.commit()
            flash('Password changed successfully.', 'success')

    return render_template('auth/change_password.html')
