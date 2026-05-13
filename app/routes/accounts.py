"""
Account management routes — create, view, detail pages.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models.account import Account
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
    summary = get_account_summary(account_id)
    if not summary:
        flash("Account not found.", "error")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("account_detail.html", summary=summary)
