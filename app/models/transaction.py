"""
Transaction model -- represents a single financial transaction in an account.
"""

from datetime import datetime, timezone
from app import db


class Transaction(db.Model):
    """
    Represents a financial transaction.

    Supported transaction types:
        - deposit: Cash deposited into the account.
        - withdrawal: Cash withdrawn from the account.
        - buy: Purchase of an asset.
        - sell: Sale of an asset.
        - dividend: Dividend received for an asset.

    Attributes:
        id: Primary key.
        account_id: Foreign key to the parent account.
        tx_type: Transaction type string.
        asset_symbol: Ticker or coin id (e.g. 'AAPL', 'bitcoin'). Null for deposit/withdrawal.
        asset_name: Human-readable asset name.
        quantity: Number of units bought/sold. Null for deposit/withdrawal.
        price_per_unit: Price paid per unit at time of transaction.
        total_amount: Total cash amount of the transaction.
        timestamp: When the transaction occurred.
        notes: Optional free-text notes.
    """

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), nullable=False
    )
    tx_type = db.Column(db.String(20), nullable=False)
    asset_symbol = db.Column(db.String(40), nullable=True)
    asset_name = db.Column(db.String(120), nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    price_per_unit = db.Column(db.Float, nullable=True)
    fee = db.Column(db.Float, nullable=True, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Transaction {self.tx_type} {self.asset_symbol} {self.total_amount}>"

    def to_dict(self):
        """Serialize transaction to a dictionary."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "tx_type": self.tx_type,
            "asset_symbol": self.asset_symbol,
            "asset_name": self.asset_name,
            "quantity": self.quantity,
            "price_per_unit": self.price_per_unit,
            "fee": self.fee or 0.0,
            "total_amount": self.total_amount,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "notes": self.notes,
        }
