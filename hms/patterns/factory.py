"""
Factory Pattern — UserRoleFactory
===================================
Dynamically creates role-specific user objects from a plain ``User``
instance.  Each concrete role class encapsulates permissions, dashboard
routing, and role-specific helper methods so that the rest of the
application can stay role-agnostic.

Usage
-----
    from hms.patterns.factory import UserRoleFactory

    role_user = UserRoleFactory.create(user)          # user is a User model
    return redirect(role_user.get_dashboard_url())
"""

from __future__ import annotations
from flask import url_for


# ======================================================================== #
#  Abstract Base Role                                                        #
# ======================================================================== #

class RoleUser:
    """
    Abstract base that wraps a ``User`` model instance and adds
    role-specific behaviour.  Attribute access falls through to the
    wrapped user so callers can treat a ``RoleUser`` like a ``User``.
    """

    ROLE: str = ""  # Override in every subclass

    def __init__(self, user):
        self._user = user

    # Transparent delegation to the underlying User
    def __getattr__(self, item):
        return getattr(self._user, item)

    # ------------------------------------------------------------------ #
    #  Interface every subclass must implement                             #
    # ------------------------------------------------------------------ #

    def get_dashboard_url(self) -> str:
        """Return the Flask ``url_for`` string for this role's dashboard."""
        raise NotImplementedError

    def get_permissions(self) -> list[str]:
        """Return a list of permission strings this role holds."""
        raise NotImplementedError

    def get_role_label(self) -> str:
        """Human-readable role label for display."""
        return self.ROLE.capitalize()

    # ------------------------------------------------------------------ #
    #  Common helpers                                                      #
    # ------------------------------------------------------------------ #

    def can(self, permission: str) -> bool:
        """Check whether this role has a specific permission string."""
        return permission in self.get_permissions()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} user_id={self._user.user_id}>"


# ======================================================================== #
#  Concrete Role Classes                                                     #
# ======================================================================== #

class AdminUser(RoleUser):
    """
    Encapsulates Admin-specific permissions and navigation.

    Admins have unrestricted access: they can manage staff, view all
    bills, generate bills, and access every section of the system.
    """

    ROLE = "admin"

    def get_dashboard_url(self) -> str:
        return url_for("admin.dashboard")

    def get_permissions(self) -> list[str]:
        return [
            "view_all_patients",
            "edit_patients",
            "delete_patients",
            "manage_staff",
            "view_all_bills",
            "generate_bills",
            "record_payments",
            "manage_pharmacy",
            "manage_appointments",
            "view_reports",
        ]

    def can_manage_staff(self) -> bool:
        return True

    def can_view_all_bills(self) -> bool:
        return True

    def can_generate_advanced_bills(self) -> bool:
        return True


class DoctorUser(RoleUser):
    """
    Encapsulates Doctor-specific permissions and navigation.

    Doctors can view their patients, write prescriptions, update
    appointment statuses, and view their own schedule.
    """

    ROLE = "doctor"

    def get_dashboard_url(self) -> str:
        return url_for("staff.doctor_dashboard")

    def get_permissions(self) -> list[str]:
        return [
            "view_own_appointments",
            "update_appointment_status",
            "write_prescriptions",
            "view_patient_records",
            "add_patients",
        ]

    def can_write_prescriptions(self) -> bool:
        return True

    def get_doctor_profile(self):
        """Lazy-load the Doctor model for this user."""
        from hms import db_operations
        return db_operations.get_doctor_by_user_id(self._user.user_id)

    def get_role_label(self) -> str:
        return "Doctor"


class PatientUser(RoleUser):
    """
    Encapsulates Patient-specific permissions and navigation.

    Patients have read-only access to their own data, can book
    appointments, and request their own bills.
    """

    ROLE = "patient"

    def get_dashboard_url(self) -> str:
        return url_for("patients.patient_dashboard")

    def get_permissions(self) -> list[str]:
        return [
            "view_own_profile",
            "book_appointments",
            "cancel_own_appointments",
            "view_own_bills",
            "request_own_bill",
            "view_own_prescriptions",
        ]

    def can_book_appointments(self) -> bool:
        return True

    def get_patient_profile(self):
        """Lazy-load the Patient model for this user."""
        from hms import db_operations
        return db_operations.get_patient_by_user_id(self._user.user_id)

    def get_role_label(self) -> str:
        return "Patient"


class NurseUser(RoleUser):
    """
    Encapsulates Nurse-specific permissions and navigation.

    Nurses can view today's appointments, manage admissions, and
    see patient records (read-only).
    """

    ROLE = "nurse"

    def get_dashboard_url(self) -> str:
        return url_for("staff.nurse_dashboard")

    def get_permissions(self) -> list[str]:
        return [
            "view_all_patients",
            "add_patients",
            "view_appointments",
            "manage_admissions",
        ]

    def get_assigned_ward(self) -> str | None:
        """Return the ward this nurse is assigned to, or None."""
        from hms import db_operations
        nurse = db_operations.get_nurse_by_user_id(self._user.user_id)
        return getattr(nurse, "assigned_ward", None) if nurse else None

    def get_role_label(self) -> str:
        return "Nurse"


class BillingUser(RoleUser):
    """
    Encapsulates Billing-staff permissions and navigation.

    Billing staff can view and generate bills, record payments,
    and export billing data.
    """

    ROLE = "billing"

    def get_dashboard_url(self) -> str:
        return url_for("admin.dashboard")

    def get_permissions(self) -> list[str]:
        return [
            "view_all_bills",
            "generate_bills",
            "generate_advanced_bills",
            "record_payments",
            "export_bills",
        ]

    def can_generate_bills(self) -> bool:
        return True

    def get_role_label(self) -> str:
        return "Billing Staff"


# ======================================================================== #
#  Factory                                                                   #
# ======================================================================== #

class UserRoleFactory:
    """
    Factory that creates the correct ``RoleUser`` subclass for a given
    ``User`` instance based on its ``role`` attribute.

    Example
    -------
    ::

        from hms.patterns.factory import UserRoleFactory

        role_user = UserRoleFactory.create(user)
        # role_user is AdminUser / DoctorUser / PatientUser / NurseUser /
        #             BillingUser depending on user.role
        return redirect(role_user.get_dashboard_url())
    """

    _registry: dict[str, type[RoleUser]] = {
        "admin":   AdminUser,
        "doctor":  DoctorUser,
        "patient": PatientUser,
        "nurse":   NurseUser,
        "billing": BillingUser,
    }

    @classmethod
    def create(cls, user) -> RoleUser:
        """
        Instantiate and return the role-specific user wrapper.

        Parameters
        ----------
        user : User
            A ``hms.models.user.User`` (or any object with a ``role``
            attribute).

        Returns
        -------
        RoleUser
            A concrete ``RoleUser`` subclass instance.

        Raises
        ------
        ValueError
            If ``user.role`` is not recognised.
        """
        role = (getattr(user, "role", "") or "").strip().lower()
        role_class = cls._registry.get(role)
        if role_class is None:
            raise ValueError(
                f"UserRoleFactory: unknown role '{role}'. "
                f"Registered roles: {list(cls._registry)}"
            )
        return role_class(user)

    @classmethod
    def register(cls, role: str, role_class: type[RoleUser]):
        """
        Register a custom role class (extension point).

        Parameters
        ----------
        role : str
            Role string (e.g. ``'pharmacist'``).
        role_class : type[RoleUser]
            Concrete subclass of ``RoleUser``.
        """
        cls._registry[role.strip().lower()] = role_class

    @classmethod
    def get_registered_roles(cls) -> list[str]:
        """Return the list of currently registered role strings."""
        return list(cls._registry.keys())
