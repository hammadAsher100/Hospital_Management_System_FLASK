"""User model — authentication, password management, role checks."""

from flask_login import UserMixin
from datetime import datetime
import bcrypt
from hms import db_operations
from hms.utils.exceptions import ValidationError


class User(UserMixin):
    """User model - compatible with Flask-Login"""

    def __init__(self, user_id: int, username: str, password_hash: str, role: str,
                 email: str, full_name: str, created_at: datetime = None,
                 last_login: datetime = None, is_active: bool = True):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.email = email
        self.full_name = full_name
        self.created_at = created_at or datetime.utcnow()
        self.last_login = last_login
        self._is_active = is_active

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        # Ensure password_hash is bytes
        if isinstance(self.password_hash, str):
            hash_bytes = self.password_hash.encode('utf-8')
        else:
            hash_bytes = self.password_hash
        return bcrypt.checkpw(password.encode('utf-8'), hash_bytes)

    def is_admin(self):
        return self.role == 'admin'

    def is_doctor(self):
        return self.role == 'doctor'

    def is_nurse(self):
        return self.role == 'nurse'

    def is_billing(self):
        return self.role == 'billing'

    def is_patient(self):
        return self.role == 'patient'

    def is_staff(self):
        return self.role in ['doctor', 'nurse', 'billing', 'admin']

    def update_last_login(self):
        db_operations.update_last_login(self.user_id)
        self.last_login = datetime.utcnow()

    def update_profile(self, full_name: str, email: str) -> bool:
        """Update user profile basics. Returns True on success."""
        updated = db_operations.update_user_profile(
            user_id=self.user_id, full_name=full_name, email=email,
        )
        if updated:
            self.full_name = full_name
            self.email = email
        return updated

    def change_password(self, current_password: str, new_password: str, confirm_password: str):
        """Validate and change user password. Raises ValidationError on failure."""
        if not self.check_password(current_password):
            raise ValidationError('Current password is incorrect.')
        if new_password != confirm_password:
            raise ValidationError('New passwords do not match.')
        if len(new_password) < 6:
            raise ValidationError('Password must be at least 6 characters.')

        self.set_password(new_password)
        updated = db_operations.update_user_password_hash(
            user_id=self.user_id, password_hash=self.password_hash,
        )
        if not updated:
            raise ValidationError('Unable to change password right now.')

    @staticmethod
    def authenticate(username: str, password: str, user_module: str = 'staff'):
        """Authenticate user and validate module access.

        Returns the User on success, raises ValidationError on failure.
        """
        user = User.get_by_username(username)
        if not user or not user.check_password(password) or not user.is_active:
            raise ValidationError('Invalid username or password.')

        if not User._validate_module_access(user, user_module):
            raise ValidationError('You do not have access to this module.')

        return user

    @staticmethod
    def _validate_module_access(user, module: str) -> bool:
        """Validate if user can access the selected module."""
        if module == 'patient':
            return user.is_patient()
        elif module == 'doctor':
            return user.is_doctor()
        elif module == 'staff':
            return user.is_staff()
        return False

    @staticmethod
    def create_account(username: str, email: str, password: str, confirm_password: str,
                       full_name: str, role: str = 'patient') -> int:
        """Create a new user account. Returns user_id. Raises ValidationError on failure."""
        if not all([username, email, password, full_name]):
            raise ValidationError('All fields are required.')
        if password != confirm_password:
            raise ValidationError('Passwords do not match.')
        if len(password) < 6:
            raise ValidationError('Password must be at least 6 characters.')

        temp_user = User(user_id=0, username=username, email=email,
                         full_name=full_name, role=role, password_hash='')
        temp_user.set_password(password)

        user_id = db_operations.create_user(
            username=username, password_hash=temp_user.password_hash,
            role=role, email=email, full_name=full_name,
        )
        if not user_id:
            raise ValidationError('Error creating user account.')
        return user_id

    @staticmethod
    def toggle_active(user_id: int):
        """Toggle user active status. Returns the updated user namespace or None."""
        return db_operations.toggle_user_active(user_id)

    @staticmethod
    def list_all():
        """List all users."""
        return db_operations.list_users()

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

    @staticmethod
    def get_by_username(username: str) -> 'User':
        """Get user by username"""
        user_data = db_operations.get_user_by_username(username)
        if not user_data:
            return None
        return User(
            user_id=user_data.user_id,
            username=user_data.username,
            password_hash=user_data.password_hash,
            role=user_data.role,
            email=user_data.email,
            full_name=user_data.full_name,
            created_at=user_data.created_at,
            last_login=user_data.last_login,
            is_active=user_data.is_active
        )

    @staticmethod
    def get_by_id(user_id: int) -> 'User':
        """Get user by ID"""
        user_data = db_operations.get_user_by_id(user_id)
        if not user_data:
            return None
        return User(
            user_id=user_data.user_id,
            username=user_data.username,
            password_hash=user_data.password_hash,
            role=user_data.role,
            email=user_data.email,
            full_name=user_data.full_name,
            created_at=user_data.created_at,
            last_login=user_data.last_login,
            is_active=user_data.is_active
        )
