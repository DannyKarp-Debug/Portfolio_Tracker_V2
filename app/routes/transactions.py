"""
Transaction routes — create and list transactions.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.validation_service import validate_transaction_data
from datetime import datetime, timezone

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/")
def list_transactions():
    """Render full transaction history, filterable by account and type."""
    account_id = request.args.get("account_id", type=int)
    tx_type = request.args.get("tx_type", "").strip().lower()

    query = Transaction.query

    if account_id:
        query = query.filter_by(account_id=account_id)
    if tx_type:
        query = query.filter_by(tx_type=tx_type)

    transactions = query.order_by(Transaction.timestamp.desc()).all()
    accounts = Account.query.order_by(Account.name).all()

    return render_template(
        "transactions.html",
        transactions=transactions,
        accounts=accounts,
        selected_account_id=account_id,
        selected_tx_type=tx_type,
    )


@transactions_bp.route("/create", methods=["GET", "POST"])
def create_transaction():
    """Handle transaction creation form display and submission."""
    accounts = Account.query.order_by(Account.name).all()

    if request.method == "POST":
        data = {
            "account_id": request.form.get("account_id"),
            "tx_type": request.form.get("tx_type"),
            "asset_symbol": request.form.get("asset_symbol"),
            "asset_name": request.form.get("asset_name"),
            "quantity": request.form.get("quantity"),
            "price_per_unit": request.form.get("price_per_unit"),
            "total_amount": request.form.get("total_amount"),
            "timestamp": request.form.get("timestamp"),
            "notes": request.form.get("notes"),
        }

        errors = validate_transaction_data(data)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "create_transaction.html", accounts=accounts, data=data
            )

        tx_type = data["tx_type"].strip().lower()

        # Compute total_amount for buy/sell from quantity * price
        if tx_type in ("buy", "sell"):
            quantity = float(data["quantity"])
            price_per_unit = float(data["price_per_unit"])
            total_amount = round(quantity * price_per_unit, 2)
        else:
            quantity = None
            price_per_unit = None
            total_amount = float(data["total_amount"])

        # Parse timestamp
        ts_str = (data.get("timestamp") or "").strip()
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        symbol = (data.get("asset_symbol") or "").strip().lower() or None
        asset_name = (data.get("asset_name") or "").strip() or symbol

        # For dividend, keep the symbol but no quantity/price
        if tx_type == "dividend":
            quantity = None
            price_per_unit = None

        tx = Transaction(
            account_id=int(data["account_id"]),
            tx_type=tx_type,
            asset_symbol=symbol,
            asset_name=asset_name,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_amount=total_amount,
            timestamp=ts,
            notes=(data.get("notes") or "").strip() or None,
        )
        db.session.add(tx)
        db.session.commit()
        flash("Transaction recorded successfully.", "success")
        return redirect(url_for("transactions.list_transactions"))

    return render_template("create_transaction.html", accounts=accounts, data={})
