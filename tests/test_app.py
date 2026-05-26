"""
Integration tests for MediCore HMS core routes.
Run with: python -m pytest tests/test_app.py -v
"""

import pytest
from hms import create_app


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as c:
        with app.app_context():
            yield c


# ── AUTH ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_page_loads(self, client):
        r = client.get("/auth/login")
        assert r.status_code == 200
        assert b"Sign In" in r.data or b"Login" in r.data

    def test_invalid_login_rejected(self, client):
        r = client.post(
            "/auth/login",
            data={"username": "nobody", "password": "wrongpass", "user_module": "staff"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"Invalid" in r.data or b"invalid" in r.data.lower()

    def test_unauthenticated_dashboard_redirects(self, client):
        r = client.get("/admin/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_signup_page_loads(self, client):
        r = client.get("/auth/signup")
        assert r.status_code == 200


# ── PATIENTS ──────────────────────────────────────────────────────────────────

class TestPatients:
    def test_patient_list_requires_login(self, client):
        r = client.get("/patients/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_patient_add_requires_login(self, client):
        r = client.get("/patients/add", follow_redirects=False)
        assert r.status_code in (301, 302)


# ── APPOINTMENTS ──────────────────────────────────────────────────────────────

class TestAppointments:
    def test_appointments_requires_login(self, client):
        r = client.get("/appointments/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_book_appointment_requires_login(self, client):
        r = client.get("/appointments/book", follow_redirects=False)
        assert r.status_code in (301, 302)


# ── BILLING ───────────────────────────────────────────────────────────────────

class TestBilling:
    def test_billing_page_requires_login(self, client):
        r = client.get("/billing/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_generate_bill_requires_login(self, client):
        r = client.get("/billing/generate", follow_redirects=False)
        assert r.status_code in (301, 302)


# ── PHARMACY ──────────────────────────────────────────────────────────────────

class TestPharmacy:
    def test_pharmacy_page_requires_login(self, client):
        r = client.get("/pharmacy/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_medicines_requires_login(self, client):
        r = client.get("/pharmacy/medicines", follow_redirects=False)
        assert r.status_code in (301, 302)


# ── STAFF ─────────────────────────────────────────────────────────────────────

class TestStaff:
    def test_staff_list_requires_login(self, client):
        r = client.get("/staff/", follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_admin_dashboard_requires_login(self, client):
        r = client.get("/admin/", follow_redirects=False)
        assert r.status_code in (301, 302)
