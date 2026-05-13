"""
Input validation service.

All form/data validation logic lives here so route handlers stay thin.
"""


VALID_TX_TYPES = {"deposit", "withdrawal", "buy", "sell", "dividend"}
VALID_ACCOUNT_TYPES = {"crypto", "stock"}


def validate_account_data(data: dict) -> list[str]:
    """
    Validate data for creating a new account.

    Args:
        data: Dict with expected keys 'name' and 'account_type'.

    Returns:
        List of error message strings. Empty list means valid.
    """
    errors = []
    name = (data.get("name") or "").strip()
    account_type = (data.get("account_type") or "").strip().lower()

    if not name:
        errors.append("Account name is required.")
    if account_type not in VALID_ACCOUNT_TYPES:
        errors.append(f"Account type must be one of: {', '.join(VALID_ACCOUNT_TYPES)}.")

    return errors


def validate_transaction_data(data: dict) -> list[str]:
    """
    Validate data for creating a new transaction.

    Rules:
        - tx_type must be one of the valid types.
        - account_id must be present and numeric.
        - For buy/sell: asset_symbol, quantity (>0), price_per_unit (>=0) required.
        - For dividend: asset_symbol and total_amount (>0) required.
        - For deposit/withdrawal: total_amount (>0) required.
        - No negative quantities or amounts.

    Args:
        data: Form data dict.

    Returns:
        List of error message strings. Empty means valid.
    """
    errors = []

    tx_type = (data.get("tx_type") or "").strip().lower()
    if tx_type not in VALID_TX_TYPES:
        errors.append(f"Transaction type must be one of: {', '.join(VALID_TX_TYPES)}.")
        return errors  # Can't validate further without knowing type

    account_id = data.get("account_id")
    if not account_id:
        errors.append("Account is required.")
    else:
        try:
            int(account_id)
        except (ValueError, TypeError):
            errors.append("Invalid account ID.")

    if tx_type in ("buy", "sell"):
        symbol = (data.get("asset_symbol") or "").strip()
        if not symbol:
            errors.append("Asset symbol/ticker is required for buy/sell.")

        quantity = data.get("quantity")
        try:
            quantity = float(quantity)
            if quantity <= 0:
                errors.append("Quantity must be greater than zero.")
        except (ValueError, TypeError):
            errors.append("Valid quantity is required for buy/sell.")

        price = data.get("price_per_unit")
        try:
            price = float(price)
            if price < 0:
                errors.append("Price per unit cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Valid price per unit is required for buy/sell.")

    elif tx_type == "dividend":
        symbol = (data.get("asset_symbol") or "").strip()
        if not symbol:
            errors.append("Asset symbol is required for dividends.")

        amount = data.get("total_amount")
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append("Dividend amount must be greater than zero.")
        except (ValueError, TypeError):
            errors.append("Valid dividend amount is required.")

    elif tx_type in ("deposit", "withdrawal"):
        amount = data.get("total_amount")
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except (ValueError, TypeError):
            errors.append("Valid amount is required.")

    return errors
