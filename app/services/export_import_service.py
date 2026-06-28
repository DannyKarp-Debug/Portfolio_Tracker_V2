"""
Account export/import service.

Keeps account portability logic out of route handlers.
"""

from datetime import datetime, timezone
from typing import Any

from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.validation_service import validate_account_data, validate_transaction_data


EXPORT_SCHEMA_VERSION = "1.0"


def export_account_payload(account_id: int) -> dict | None:
    """Build a portable JSON payload for a single account and all of its transactions."""
    account = db.session.get(Account, account_id)
    if not account:
        return None

    txs = (
        Transaction.query.filter_by(account_id=account_id)
        .order_by(Transaction.timestamp.asc(), Transaction.id.asc())
        .all()
    )

    tx_payload = []
    for tx in txs:
        tx_dict = tx.to_dict()
        tx_dict.pop("id", None)
        tx_dict.pop("account_id", None)
        tx_payload.append(tx_dict)

    return {
        "version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "name": account.name,
            "account_type": account.account_type,
        },
        "transactions": tx_payload,
        "metadata": {
            "transaction_count": len(tx_payload),
        },
    }


def import_account_payload(
    payload: dict,
    target_mode: str,
    existing_account_id: int | None = None,
) -> dict:
    """Import account payload into a new or existing account with partial-row handling."""
    result = {
        "fatal_error": None,
        "account_id": None,
        "account_name": None,
        "imported_count": 0,
        "skipped_count": 0,
        "row_errors": [],
    }

    fatal = _validate_payload_shape(payload)
    if fatal:
        result["fatal_error"] = fatal
        return result

    account_payload = payload["account"]
    tx_rows = payload["transactions"]
    mode = (target_mode or "").strip().lower()

    account, fatal_error = _resolve_import_target(mode, account_payload, existing_account_id)
    if fatal_error:
        result["fatal_error"] = fatal_error
        return result
    if account is None:
        result["fatal_error"] = "Import target could not be resolved."
        return result

    normalized_rows = []
    for idx, row in enumerate(tx_rows, start=1):
        row_tx, row_errors = _normalize_and_validate_row(row, account.id, idx)
        if row_errors:
            result["row_errors"].extend(row_errors)
            result["skipped_count"] += 1
            continue
        normalized_rows.append(row_tx)

    normalized_rows.sort(key=lambda item: item["timestamp"])

    if normalized_rows:
        db.session.add_all([Transaction(**row) for row in normalized_rows])
        db.session.commit()

    result["account_id"] = account.id
    result["account_name"] = account.name
    result["imported_count"] = len(normalized_rows)
    return result


def _validate_payload_shape(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return "Invalid payload: top-level JSON object is required."
    if not payload.get("version"):
        return "Invalid payload: missing 'version'."
    if not isinstance(payload.get("account"), dict):
        return "Invalid payload: missing or invalid 'account' object."
    if not isinstance(payload.get("transactions"), list):
        return "Invalid payload: 'transactions' must be a list."
    return None


def _resolve_import_target(
    mode: str, account_payload: dict, existing_account_id: int | None
) -> tuple[Account | None, str | None]:
    if mode == "append_existing":
        if not existing_account_id:
            return None, "Please choose an existing account to append into."
        account = db.session.get(Account, existing_account_id)
        if not account:
            return None, "Selected existing account was not found."

        incoming_type = (account_payload.get("account_type") or "").strip().lower()
        if incoming_type and account.account_type != incoming_type:
            return (
                None,
                "Account type mismatch: imported account type does not match the selected target account.",
            )
        return account, None

    if mode != "create_new":
        return None, "Invalid import mode."

    candidate_name = (account_payload.get("name") or "").strip()
    candidate_type = (account_payload.get("account_type") or "").strip().lower()

    validation_errors = validate_account_data(
        {"name": candidate_name, "account_type": candidate_type}
    )
    if validation_errors:
        return None, validation_errors[0]

    if Account.query.filter_by(name=candidate_name).first():
        return (
            None,
            "Account name already exists. Rename the account and try importing again.",
        )

    account = Account()
    account.name = candidate_name
    account.account_type = candidate_type
    db.session.add(account)
    db.session.commit()
    return account, None


def _normalize_and_validate_row(row: dict, account_id: int, idx: int) -> tuple[dict | None, list[str]]:
    errors = []
    if not isinstance(row, dict):
        return None, [f"Row {idx}: each transaction must be a JSON object."]

    tx_type = (row.get("tx_type") or "").strip().lower()
    symbol = (row.get("asset_symbol") or "").strip().lower()
    asset_name = (row.get("asset_name") or "").strip() or symbol or None
    notes = (row.get("notes") or "").strip() or None

    validation_data = {
        "account_id": str(account_id),
        "tx_type": tx_type,
        "asset_symbol": symbol,
        "quantity": row.get("quantity"),
        "price_per_unit": row.get("price_per_unit"),
        "total_amount": row.get("total_amount"),
    }
    row_validation_errors = validate_transaction_data(validation_data)
    if row_validation_errors:
        for err in row_validation_errors:
            errors.append(f"Row {idx}: {err}")
        return None, errors

    ts = _parse_timestamp(row.get("timestamp"))
    if ts is None:
        return None, [f"Row {idx}: invalid timestamp."]

    if tx_type in ("buy", "sell"):
        quantity = _safe_float(row.get("quantity"))
        price_per_unit = _safe_float(row.get("price_per_unit"))
        total_amount = round(quantity * price_per_unit, 2)
        fee = round(_safe_float(row.get("fee"), default=0.0), 2)
    elif tx_type == "dividend":
        quantity = None
        price_per_unit = None
        fee = 0.0
        total_amount = _safe_float(row.get("total_amount"))
    else:
        quantity = None
        price_per_unit = None
        fee = 0.0
        total_amount = _safe_float(row.get("total_amount"))

    return {
        "account_id": account_id,
        "tx_type": tx_type,
        "asset_symbol": symbol or None,
        "asset_name": asset_name,
        "quantity": quantity,
        "price_per_unit": price_per_unit,
        "fee": fee,
        "total_amount": total_amount,
        "timestamp": ts,
        "notes": notes,
    }, []


def _parse_timestamp(raw_value) -> datetime | None:
    if raw_value is None:
        return datetime.now(timezone.utc)

    ts_text = str(raw_value).strip()
    if not ts_text:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(ts_text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)