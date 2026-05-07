import unittest


class TestFactoryPattern(unittest.TestCase):
    def test_user_role_factory_creates_expected_wrapper(self):
        from hms.patterns.factory import UserRoleFactory, AdminUser, DoctorUser, PatientUser

        class FakeUser:
            def __init__(self, user_id, role):
                self.user_id = user_id
                self.role = role
                self.username = f"user{user_id}"

        self.assertIsInstance(UserRoleFactory.create(FakeUser(1, "admin")), AdminUser)
        self.assertIsInstance(UserRoleFactory.create(FakeUser(2, "doctor")), DoctorUser)
        self.assertIsInstance(UserRoleFactory.create(FakeUser(3, "patient")), PatientUser)

    def test_user_role_factory_rejects_unknown_role(self):
        from hms.patterns.factory import UserRoleFactory

        class FakeUser:
            user_id = 1
            username = "x"
            role = "unknown_role"

        with self.assertRaises(ValueError):
            UserRoleFactory.create(FakeUser())


class TestDecoratorPattern(unittest.TestCase):
    def test_decorator_total_and_items(self):
        from hms.patterns.decorator import BillingDecoratorBuilder

        builder = (
            BillingDecoratorBuilder("Consultation Fee", base_amount=500.0)
            .add_lab_test(amount=200.0, test_name="CBC")
            .add_room_charge(amount=1500.0, room_type="General Ward", days=2)
            .add_icu_fee(amount=5000.0, days=1)
            .add_emergency_service(amount=800.0)
        )
        expected_total = 500.0 + 200.0 + (1500.0 * 2) + (5000.0 * 1) + 800.0
        self.assertAlmostEqual(builder.get_total(), expected_total, places=6)

        items = builder.get_bill_items()
        self.assertGreaterEqual(len(items), 5)
        self.assertTrue(all("description" in i and "quantity" in i and "unit_price" in i for i in items))


class TestChainOfResponsibilityPattern(unittest.TestCase):
    def test_patient_request_chain_enriches_context(self):
        from hms.patterns.chain_of_responsibility import PatientRequestChain

        ctx = {
            "patient_id": 42,
            "request_type": "appointment",
            "priority": "urgent",
            "reason": "Urgent fever",
            "diagnosis": "",
            "bill_id": None,
        }
        result = PatientRequestChain().process(ctx)
        self.assertIn("triage_level", result)
        self.assertIn("diagnosis_status", result)
        self.assertIn("billing_status", result)
        self.assertIn("summary", result)
        self.assertIn("handler_log", result)
        self.assertIsInstance(result["handler_log"], list)


if __name__ == "__main__":
    unittest.main()

