import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_database_uri():
    return (
        os.environ.get("BILLZY_DATABASE_URI")
        or os.environ.get("DATABASE_URL")
        or "sqlite:///" + os.path.join(BASE_DIR, "instance", "billzy.db")
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "billzy-dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # FR-1.2: sessions auto-expire after 30 minutes of inactivity
    PERMANENT_SESSION_LIFETIME_MINUTES = 30

    # Business logic
    RETURN_WINDOW_DAYS = 30  # Return Policy Validation
