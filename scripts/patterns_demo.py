"""
Run-time demo for the design patterns implemented in this HMS project.

This script is intentionally safe to run even when SQL Server isn't available:
- Singleton(DB) demo will attempt to open a connection only if it can load
  DB params from config; otherwise it prints a skip message.
- Factory / Decorator / Chain demos are pure-Python and always run.

Run:
  python scripts/patterns_demo.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


# Ensure `import hms` works when running from scripts/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def demo_factory() -> None:
    from hms.patterns.factory import UserRoleFactory

    @dataclass
    class FakeUser:
        user_id: int
        username: str
        role: str

    users = [
        FakeUser(1, "alice", "admin"),
        FakeUser(2, "dr_bob", "doctor"),
        FakeUser(3, "carol", "patient"),
    ]

    print("\n=== Factory Pattern Demo ===")
    print("Creates role objects (AdminUser/DoctorUser/PatientUser) from a plain user.")
    for u in users:
        role_user = UserRoleFactory.create(u)
        print(f"- {u.username} ({u.role}) -> {role_user.__class__.__name__}, label='{role_user.get_role_label()}'")


def demo_decorator() -> None:
    from hms.patterns.decorator import BillingDecoratorBuilder

    print("\n=== Decorator Pattern Demo ===")
    builder = (
        BillingDecoratorBuilder("Consultation Fee", base_amount=500.0)
        .add_lab_test(amount=200.0, test_name="CBC")
        .add_room_charge(amount=1500.0, room_type="General Ward", days=2)
        .add_emergency_service(amount=800.0)
    )
    print(builder.get_description())
    print(f"Total: {builder.get_total():,.2f}")
    print("Line items:")
    for item in builder.get_bill_items():
        print(f"  - {item['description']} x{item['quantity']} @ {item['unit_price']}")


def demo_chain_of_responsibility() -> None:
    from hms.patterns.chain_of_responsibility import PatientRequestChain

    print("\n=== Chain of Responsibility Demo ===")
    ctx = {
        "patient_id": 42,
        "request_type": "appointment",
        "priority": "urgent",
        "reason": "Urgent chest pain",
        "diagnosis": "",
        "bill_id": None,
    }
    result = PatientRequestChain().process(ctx)
    print("Summary:", result.get("summary"))
    print("Handler log:")
    for line in result.get("handler_log", []):
        print(" ", line)


def demo_singleton_db() -> None:
    print("\n=== Singleton Pattern Demo (Database) ===")
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from hms.patterns.singleton import DatabaseSingleton

        db_url = os.environ.get('DATABASE_URL', '')
        if not db_url:
            print("Skipping: DATABASE_URL not configured in environment.")
            return

        singleton = DatabaseSingleton.get_instance({})
        conn = singleton.get_connection()

        print("Singleton instance:", singleton)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        print("Connection probe OK (SELECT 1).")
    except Exception as exc:
        print(f"DB singleton demo could not run: {exc}")


def main() -> None:
    demo_factory()
    demo_decorator()
    demo_chain_of_responsibility()
    demo_singleton_db()


if __name__ == "__main__":
    main()

