"""
Account management routes — create, view, detail, rename, delete.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.portfolio_service import get_account_summary
from app.services.validation_service import validate_account_data

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/")
def list_accounts():
    """Render the list of all accounts."""
    accounts = Account.query.order_by(Account.created_at.desc()).all()
    return render_template("accounts.html", accounts=accounts)


@accounts_bp.route("/create", methods=["GET", "POST"])
def create_account():
    """Handle account creation form display and submission."""
    if request.method == "POST":
        data = {
            "name": request.form.get("name"),
            "account_type": request.form.get("account_type"),
        }
        errors = validate_account_data(data)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("create_account.html", data=data)

        account = Account(
            name=data["name"].strip(),
            account_type=data["account_type"].strip().lower(),
        )
        db.session.add(account)
        db.session.commit()
        flash(f"Account '{account.name}' created successfully.", "success")
        return redirect(url_for("accounts.list_accounts"))

    return render_template("create_account.html", data={})


@accounts_bp.route("/<int:account_id>")
def account_detail(account_id):
    """Render detail page for a single account with holdings and summary."""
    summary = get_account_summary(account_id, skip_prices=True)
    if not summary:
        flash("Account not found.", "error")
        return redirect(url_for("accounts.list_accounts"))
    latest_tx = Transaction.query.order_by(Transaction.timestamp.desc()).first()
    last_tx_ts = latest_tx.timestamp.isoformat() if latest_tx else ""
    return render_template("account_detail.html", summary=summary, last_tx_ts=last_tx_ts)


@accounts_bp.route("/<int:account_id>/rename", methods=["POST"])
def rename_account(account_id):
    """Rename an account."""
    account = db.session.get(Account, account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("accounts.list_accounts"))

    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Account name cannot be empty.", "error")
        return redirect(url_for("accounts.account_detail", account_id=account_id))
    if len(new_name) > 120:
        flash("Account name must be 120 characters or fewer.", "error")
        return redirect(url_for("accounts.account_detail", account_id=account_id))

    old_name = account.name
    account.name = new_name
    db.session.commit()
    flash(f"Account renamed from '{old_name}' to '{new_name}'.", "success")
    return redirect(url_for("accounts.account_detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/delete", methods=["POST"])
def delete_account(account_id):
    """Delete an account and all its transactions."""
    account = db.session.get(Account, account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("accounts.list_accounts"))

    name = account.name
    db.session.delete(account)
    db.session.commit()
    flash(f"Account '{name}' and all its transactions have been deleted.", "success")
    return redirect(url_for("accounts.list_accounts"))
