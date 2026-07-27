import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def normalize_sqlite_uri(uri: str) -> str:
    if uri.startswith("sqlite:"):
        return uri

    path = os.path.abspath(uri)
    unix_path = path.replace("\\", "/")
    return f"sqlite:///{unix_path}"


def get_database_uri():
    raw_uri = os.environ.get("BILLZY_DATABASE_URI") or os.environ.get("DATABASE_URL")
    if raw_uri:
        return normalize_sqlite_uri(raw_uri)

    return "sqlite:///" + os.path.join(BASE_DIR, "instance", "billzy.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "billzy-dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # FR-1.2: sessions auto-expire after 30 minutes of inactivity
    PERMANENT_SESSION_LIFETIME_MINUTES = 30

    # Business logic
    RETURN_WINDOW_DAYS = 30  # Return Policy Validation
