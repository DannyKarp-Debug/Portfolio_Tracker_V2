"""
Application factory for the Portfolio Tracker Flask app.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class to use. Defaults to Config.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.routes.dashboard import dashboard_bp
    from app.routes.accounts import accounts_bp
    from app.routes.transactions import transactions_bp
    from app.routes.api import api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(transactions_bp, url_prefix="/transactions")
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        from app.models import account, transaction
        db.create_all()
        _migrate_add_fee_column(app)

    return app


def _migrate_add_fee_column(app):
    """Add the 'fee' column to transactions if it doesn't exist yet."""
    from sqlalchemy import text, inspect
    with app.app_context():
        inspector = inspect(db.engine)
        cols = [c["name"] for c in inspector.get_columns("transactions")]
        if "fee" not in cols:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN fee FLOAT DEFAULT 0.0"))
                conn.commit()
