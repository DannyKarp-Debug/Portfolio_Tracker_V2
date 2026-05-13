"""
Portfolio calculation service.

Computes holdings, P&L, cost basis, portfolio weights, and best/worst
investments from raw transaction data. All business logic lives here —
route handlers should only call these functions.
"""

from collections import defaultdict
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.price_service import (
    fetch_bulk_crypto_prices,
    fetch_bulk_stock_prices,
)


def compute_holdings_for_account(account_id: int) -> list[dict]:
    """
    Compute current holdings for a single account from its transactions.

    Processes buy/sell/dividend transactions to determine quantity held
    and average cost basis per asset.

    Args:
        account_id: The account to compute holdings for.

    Returns:
        List of holding dicts with keys: asset_symbol, asset_name,
        quantity, avg_cost, total_invested, dividends_received.
    """
    transactions = (
        Transaction.query
        .filter_by(account_id=account_id)
        .order_by(Transaction.timestamp.asc())
        .all()
    )

    holdings: dict[str, dict] = {}

    for tx in transactions:
        sym = tx.asset_symbol
        if sym is None:
            continue

        if sym not in holdings:
            holdings[sym] = {
                "asset_symbol": sym,
                "asset_name": tx.asset_name or sym,
                "quantity": 0.0,
                "total_cost": 0.0,
                "dividends_received": 0.0,
                "realized_pnl": 0.0,
            }

        h = holdings[sym]

        if tx.tx_type == "buy":
            qty = tx.quantity or 0.0
            cost = tx.total_amount or 0.0
            h["total_cost"] += cost
            h["quantity"] += qty

        elif tx.tx_type == "sell":
            qty = tx.quantity or 0.0
            if h["quantity"] > 0:
                avg_cost = h["total_cost"] / h["quantity"]
                cost_of_sold = avg_cost * qty
                sale_proceeds = tx.total_amount or 0.0
                h["realized_pnl"] += sale_proceeds - cost_of_sold
                h["total_cost"] -= cost_of_sold
                h["quantity"] -= qty
                if h["quantity"] < 1e-12:
                    h["quantity"] = 0.0
                    h["total_cost"] = 0.0

        elif tx.tx_type == "dividend":
            h["dividends_received"] += tx.total_amount or 0.0

    result = []
    for sym, h in holdings.items():
        avg_cost = (h["total_cost"] / h["quantity"]) if h["quantity"] > 0 else 0.0
        result.append({
            "asset_symbol": h["asset_symbol"],
            "asset_name": h["asset_name"],
            "quantity": round(h["quantity"], 8),
            "avg_cost": round(avg_cost, 4),
            "total_invested": round(h["total_cost"], 2),
            "dividends_received": round(h["dividends_received"], 2),
            "realized_pnl": round(h["realized_pnl"], 2),
        })

    return result


def enrich_holdings_with_prices(holdings: list[dict], account_type: str) -> list[dict]:
    """
    Attach current market prices and P&L calculations to holdings.

    Also tags each holding with its account_type so the UI can dispatch
    chart requests to the correct price feed.

    Args:
        holdings: List of holding dicts from compute_holdings_for_account.
        account_type: 'crypto' or 'stock'.

    Returns:
        The same list with additional keys: current_price, current_value,
        unrealized_pnl, unrealized_pnl_pct, account_type, weight.
    """
    symbols = [h["asset_symbol"] for h in holdings if h["quantity"] > 0]

    if account_type == "crypto":
        prices = fetch_bulk_crypto_prices(symbols)
    else:
        prices = fetch_bulk_stock_prices(symbols)

    total_value = 0.0
    for h in holdings:
        h["account_type"] = account_type
        sym = h["asset_symbol"]
        price = prices.get(sym)
        h["current_price"] = round(price, 4) if price else None

        if price and h["quantity"] > 0:
            current_val = price * h["quantity"]
            h["current_value"] = round(current_val, 2)
            unrealized = current_val - h["total_invested"]
            h["unrealized_pnl"] = round(unrealized, 2)
            if h["total_invested"] > 0:
                h["unrealized_pnl_pct"] = round(
                    (unrealized / h["total_invested"]) * 100, 2
                )
            else:
                h["unrealized_pnl_pct"] = 0.0
            total_value += current_val
        else:
            h["current_value"] = 0.0
            h["unrealized_pnl"] = 0.0
            h["unrealized_pnl_pct"] = 0.0

    for h in holdings:
        if total_value > 0 and h["current_value"] > 0:
            h["weight"] = round((h["current_value"] / total_value) * 100, 2)
        else:
            h["weight"] = 0.0

    return holdings


def compute_cash_balance(account_id: int) -> float:
    """
    Compute the cash balance for an account.

    Cash increases on deposits, sell proceeds, and dividends.
    Cash decreases on withdrawals and buy costs.

    Args:
        account_id: The account to compute cash for.

    Returns:
        Current cash balance as a float.
    """
    transactions = Transaction.query.filter_by(account_id=account_id).all()
    cash = 0.0
    for tx in transactions:
        if tx.tx_type == "deposit":
            cash += tx.total_amount or 0.0
        elif tx.tx_type == "withdrawal":
            cash -= tx.total_amount or 0.0
        elif tx.tx_type == "buy":
            cash -= tx.total_amount or 0.0
        elif tx.tx_type == "sell":
            cash += tx.total_amount or 0.0
        elif tx.tx_type == "dividend":
            cash += tx.total_amount or 0.0
    return round(cash, 2)


def get_account_summary(account_id: int) -> dict:
    """
    Build a full summary for one account: holdings, cash, totals.

    Args:
        account_id: The account to summarize.

    Returns:
        Dict with keys: account, holdings, cash_balance,
        total_value, total_invested, total_pnl, total_pnl_pct.
    """
    from app import db as _db
    account = _db.session.get(Account, account_id)
    if not account:
        return {}

    holdings = compute_holdings_for_account(account_id)
    holdings = enrich_holdings_with_prices(holdings, account.account_type)
    cash = compute_cash_balance(account_id)

    total_value = sum(h["current_value"] for h in holdings) + cash
    total_invested = _total_deposits(account_id)
    total_pnl = total_value - total_invested
    total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0.0

    return {
        "account": account.to_dict(),
        "holdings": [h for h in holdings if h["quantity"] > 0],
        "cash_balance": cash,
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }


def get_combined_dashboard() -> dict:
    """
    Build a unified dashboard combining all accounts.

    Returns:
        Dict with keys: accounts (list of summaries), total_value,
        total_invested, total_pnl, total_pnl_pct, all_holdings,
        best_investment, worst_investment.
    """
    accounts = Account.query.all()
    summaries = []
    all_holdings = []
    grand_total_value = 0.0
    grand_total_invested = 0.0

    for acct in accounts:
        summary = get_account_summary(acct.id)
        if summary:
            summaries.append(summary)
            grand_total_value += summary["total_value"]
            grand_total_invested += summary["total_invested"]
            all_holdings.extend(summary["holdings"])

    grand_pnl = grand_total_value - grand_total_invested
    grand_pnl_pct = (
        round((grand_pnl / grand_total_invested) * 100, 2)
        if grand_total_invested > 0
        else 0.0
    )

    # Recompute weights against the grand total
    for h in all_holdings:
        if grand_total_value > 0 and h["current_value"] > 0:
            h["weight"] = round((h["current_value"] / grand_total_value) * 100, 2)
        else:
            h["weight"] = 0.0

    best, worst = _find_best_worst(all_holdings)

    return {
        "accounts": summaries,
        "total_value": round(grand_total_value, 2),
        "total_invested": round(grand_total_invested, 2),
        "total_pnl": round(grand_pnl, 2),
        "total_pnl_pct": grand_pnl_pct,
        "all_holdings": all_holdings,
        "best_investment": best,
        "worst_investment": worst,
    }


def get_portfolio_value_history(current_total: float | None = None) -> list[dict]:
    """
    Build a time series of the portfolio's total value based on transactions.

    For each transaction date, compute the cumulative cash position.
    The current real portfolio value (including asset appreciation) is
    appended as today's data point.

    Args:
        current_total: Pre-computed current portfolio total value.
            If None, fetches it via get_combined_dashboard().

    Returns:
        List of dicts with 'date' and 'value' keys, sorted chronologically.
    """
    from sqlalchemy import func
    from app import db as _db
    from datetime import date

    rows = (
        _db.session.query(
            func.date(Transaction.timestamp).label("day"),
            func.sum(
                _db.case(
                    (Transaction.tx_type == "deposit", Transaction.total_amount),
                    (Transaction.tx_type == "withdrawal", -Transaction.total_amount),
                    (Transaction.tx_type == "buy", -Transaction.total_amount),
                    (Transaction.tx_type == "sell", Transaction.total_amount),
                    (Transaction.tx_type == "dividend", Transaction.total_amount),
                    else_=0,
                )
            ).label("net"),
        )
        .group_by(func.date(Transaction.timestamp))
        .order_by(func.date(Transaction.timestamp))
        .all()
    )

    series = []
    cumulative = 0.0
    for day, net in rows:
        cumulative += float(net)
        series.append({"date": str(day), "value": round(cumulative, 2)})

    # Append current real value as today's data point
    if current_total is None:
        dashboard = get_combined_dashboard()
        current_total = dashboard["total_value"]

    today = date.today().isoformat()
    if series and series[-1]["date"] == today:
        series[-1]["value"] = current_total
    else:
        series.append({"date": today, "value": current_total})

    return series


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _total_deposits(account_id: int) -> float:
    """
    Sum of all deposits minus withdrawals for an account (net capital invested).

    Args:
        account_id: Account to compute for.

    Returns:
        Net deposited cash as a float.
    """
    txs = Transaction.query.filter_by(account_id=account_id).all()
    total = 0.0
    for tx in txs:
        if tx.tx_type == "deposit":
            total += tx.total_amount or 0.0
        elif tx.tx_type == "withdrawal":
            total -= tx.total_amount or 0.0
    return total


def _find_best_worst(holdings: list[dict]) -> tuple[dict | None, dict | None]:
    """
    Find the best and worst performing investments by total return %.

    Combines realized P&L (from sells) and unrealized P&L (from current
    market value vs cost basis) to determine a total return percentage.

    Args:
        holdings: Enriched holdings list.

    Returns:
        Tuple of (best_holding, worst_holding). Either may be None.
    """
    scored = []
    for h in holdings:
        realized = h.get("realized_pnl", 0.0)
        unrealized = h.get("unrealized_pnl", 0.0)
        invested = h.get("total_invested", 0.0)
        total_return = realized + unrealized
        if invested > 0:
            total_return_pct = round((total_return / invested) * 100, 2)
        else:
            total_return_pct = h.get("unrealized_pnl_pct", 0.0)
        scored.append((total_return_pct, h))

    if not scored:
        return None, None

    scored.sort(key=lambda x: x[0])
    worst = scored[0][1]
    best = scored[-1][1]
    return best, worst
