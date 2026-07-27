import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, session
from flask_login import current_user

from config import Config
from extensions import db, login_manager
from models import User, Shop, ROLE_SUPER_ADMIN


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # FR-1.2: enforce 30-minute inactivity session expiry
    @app.before_request
    def make_session_permanent():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(
            minutes=app.config["PERMANENT_SESSION_LIFETIME_MINUTES"]
        )

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.inventory import inventory_bp
    from blueprints.billing import billing_bp
    from blueprints.finance import finance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(finance_bp)

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user}

    with app.app_context():
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if db_uri.startswith("sqlite:///"):
            sqlite_path = db_uri.replace("sqlite:///", "")
            sqlite_dir = os.path.dirname(sqlite_path)
            if sqlite_dir:
                Path(sqlite_dir).mkdir(parents=True, exist_ok=True)

        db.create_all()
        _seed_super_admin()

    return app


def _seed_super_admin():
    """Creates a default Super Admin on first run (change password immediately)."""
    if not User.query.filter_by(role=ROLE_SUPER_ADMIN).first():
        admin = User(name="Super Admin", email="admin@billzy.local", role=ROLE_SUPER_ADMIN)
        admin.set_password("ChangeMe123!")
        db.session.add(admin)
        db.session.commit()
        print("Seeded Super Admin -> email: admin@billzy.local | password: ChangeMe123!")


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
