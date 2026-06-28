"""
Account management routes — create, view, detail, rename, delete.
"""

import json
import re
from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.portfolio_service import get_account_summary
from app.services.validation_service import validate_account_data
from app.services.export_import_service import export_account_payload, import_account_payload

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


@accounts_bp.route("/<int:account_id>/export", methods=["GET"])
def export_account(account_id):
    """Export a single account and its transactions as a JSON file."""
    payload = export_account_payload(account_id)
    if not payload:
        flash("Account not found.", "error")
        return redirect(url_for("accounts.list_accounts"))

    account_name = payload["account"]["name"]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", account_name).strip("-") or "account"
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{slug}-{date_part}.json"

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    return send_file(
        BytesIO(json_bytes),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@accounts_bp.route("/import", methods=["GET", "POST"])
def import_account():
    """Import account data from a JSON export file."""
    accounts = Account.query.order_by(Account.name).all()
    data = {
        "target_mode": "create_new",
        "existing_account_id": "",
    }

    if request.method == "POST":
        data["target_mode"] = (request.form.get("target_mode") or "create_new").strip()
        data["existing_account_id"] = (request.form.get("existing_account_id") or "").strip()

        uploaded = request.files.get("import_file")
        if not uploaded or not uploaded.filename:
            flash("Please choose a JSON file to import.", "error")
            return render_template("import_account.html", accounts=accounts, data=data)

        try:
            payload = json.loads(uploaded.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            flash("Invalid JSON file. Please upload a valid account export file.", "error")
            return render_template("import_account.html", accounts=accounts, data=data)

        existing_account_id = None
        if data["target_mode"] == "append_existing":
            try:
                existing_account_id = int(data["existing_account_id"])
            except (TypeError, ValueError):
                flash("Please choose a valid existing account.", "error")
                return render_template("import_account.html", accounts=accounts, data=data)

        result = import_account_payload(
            payload,
            target_mode=data["target_mode"],
            existing_account_id=existing_account_id,
        )

        if result.get("fatal_error"):
            flash(result["fatal_error"], "error")
            return render_template("import_account.html", accounts=accounts, data=data)

        imported_count = result["imported_count"]
        skipped_count = result["skipped_count"]
        account_name = result["account_name"]

        flash(
            f"Import complete for '{account_name}': {imported_count} transaction(s) imported, "
            f"{skipped_count} skipped.",
            "success",
        )

        row_errors = result.get("row_errors", [])
        for err in row_errors[:10]:
            flash(err, "error")
        if len(row_errors) > 10:
            flash(f"...and {len(row_errors) - 10} more row error(s).", "error")

        return redirect(url_for("accounts.account_detail", account_id=result["account_id"]))

    return render_template("import_account.html", accounts=accounts, data=data)
