import os
import unittest
from importlib import reload
from unittest.mock import patch

from app import create_app
from extensions import db
from models import User, Shop, Product, ROLE_BUSINESSMAN, ROLE_STORE_MANAGER, ROLE_BILLING_OPERATOR


class PasswordResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

    def test_reset_password_updates_existing_user(self):
        user = User(name="Test User", email="user@example.com", role="businessman")
        user.set_password("oldpass123")
        db.session.add(user)
        db.session.commit()

        response = self.client.post(
            "/forgot-password",
            data={
                "email": "user@example.com",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password updated successfully", response.get_data())

        updated_user = db.session.get(User, user.id)
        self.assertTrue(updated_user.check_password("newpass123"))
        self.assertFalse(updated_user.check_password("oldpass123"))

    def test_profile_page_loads_and_updates_user_info(self):
        user = User(name="Test User", email="user@example.com", role="businessman")
        user.set_password("oldpass123")
        db.session.add(user)
        db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"My Profile", response.get_data())

        response = self.client.post(
            "/profile",
            data={
                "name": "Updated Name",
                "email": "updated@example.com",
                "phone": "1234567890",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully", response.get_data())

        updated_user = db.session.get(User, user.id)
        self.assertEqual(updated_user.name, "Updated Name")
        self.assertEqual(updated_user.email, "updated@example.com")
        self.assertEqual(updated_user.phone, "1234567890")

    def test_staff_edit_and_delete_actions_work(self):
        owner = User(name="Owner", email="owner@example.com", role=ROLE_BUSINESSMAN)
        owner.set_password("ownerpass123")
        db.session.add(owner)
        db.session.flush()

        shop = Shop(name="Test Shop", owner_id=owner.id, state="MH", gstin="1234")
        db.session.add(shop)
        db.session.flush()
        owner.shop_id = shop.id

        staff_user = User(
            name="Old Staff",
            email="staff@example.com",
            role=ROLE_STORE_MANAGER,
            shop_id=shop.id,
        )
        staff_user.set_password("staffpass123")
        db.session.add(staff_user)
        db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(owner.id)
            session["_fresh"] = True

        response = self.client.post(
            "/staff",
            data={"action": "prepare_edit", "staff_id": staff_user.id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Edit Staff Member", response.get_data())

        response = self.client.post(
            "/staff",
            data={
                "action": "edit",
                "staff_id": staff_user.id,
                "name": "Updated Staff",
                "email": "updated@example.com",
                "role": ROLE_BILLING_OPERATOR,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Staff member updated successfully", response.get_data())

        updated_staff = db.session.get(User, staff_user.id)
        self.assertEqual(updated_staff.name, "Updated Staff")
        self.assertEqual(updated_staff.email, "updated@example.com")
        self.assertEqual(updated_staff.role, ROLE_BILLING_OPERATOR)

        response = self.client.post(
            "/staff",
            data={"action": "delete", "staff_id": staff_user.id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Staff member deleted successfully", response.get_data())

        self.assertIsNone(db.session.get(User, staff_user.id))

    def test_notification_dropdown_renders_for_authenticated_users(self):
        user = User(name="Test User", email="user@example.com", role="businessman")
        user.set_password("oldpass123")
        db.session.add(user)
        db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('id="notificationsDropdown"', html)
        self.assertIn('data-bs-toggle="dropdown"', html)
        self.assertIn("No new notifications", html)

    def test_billing_checkout_creates_notification(self):
        owner = User(name="Owner", email="owner@example.com", role=ROLE_BUSINESSMAN)
        owner.set_password("ownerpass123")
        db.session.add(owner)
        db.session.flush()

        shop = Shop(name="Test Shop", owner_id=owner.id, state="MH", gstin="1234")
        db.session.add(shop)
        db.session.flush()
        owner.shop_id = shop.id

        product = Product(
            shop_id=shop.id,
            name="Test Product",
            sku="SKU1",
            cost_price=50,
            selling_price=100,
            tax_rate=10,
            stock_qty=10,
        )
        db.session.add(product)
        db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(owner.id)
            session["_fresh"] = True
            session["pos_cart"] = {str(product.id): 1}

        response = self.client.post(
            "/billing/checkout",
            data={"payment_mode": "Cash"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            notifications = session.get("notifications", [])

        self.assertTrue(notifications)
        self.assertIn("bill", notifications[0]["message"].lower())
        self.assertFalse(notifications[0]["read"])

    def test_config_uses_database_uri_from_environment(self):
        with patch.dict(os.environ, {"BILLZY_DATABASE_URI": "sqlite:///C:/shared/billzy.db"}, clear=False):
            import config

            reload(config)
            self.assertEqual(config.Config.SQLALCHEMY_DATABASE_URI, "sqlite:///C:/shared/billzy.db")

    def test_config_normalizes_windows_path(self):
        with patch.dict(os.environ, {"BILLZY_DB_PATH": "C:\\shared\\billzy.db"}, clear=False):
            import config

            reload(config)
            self.assertTrue(config.Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///"))
            self.assertIn("C:/shared/billzy.db", config.Config.SQLALCHEMY_DATABASE_URI)


if __name__ == "__main__":
    unittest.main()
