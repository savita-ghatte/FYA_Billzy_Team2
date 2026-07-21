import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "billzy-dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "billzy.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # FR-1.2: sessions auto-expire after 30 minutes of inactivity
    PERMANENT_SESSION_LIFETIME_MINUTES = 30

    # Business logic
    RETURN_WINDOW_DAYS = 30  # Return Policy Validation
