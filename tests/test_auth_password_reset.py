import os
import unittest
from importlib import reload
from unittest.mock import patch

from app import create_app
from extensions import db
from models import User


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
