"""
Account model — represents a portfolio account (Crypto or Stock/ETF).
"""

from datetime import datetime, timezone
from app import db


class Account(db.Model):
    """
    Represents a portfolio account.

    Attributes:
        id: Primary key.
        name: Human-readable account name.
        account_type: Either 'crypto' or 'stock'.
        created_at: Timestamp of account creation.
        transactions: Relationship to associated transactions.
    """

    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    transactions = db.relationship(
        "Transaction", backref="account", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Account {self.name} ({self.account_type})>"

    def to_dict(self):
        """Serialize account to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "account_type": self.account_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
