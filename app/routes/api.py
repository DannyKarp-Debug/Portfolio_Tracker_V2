"""
JSON API routes -- used by the frontend JavaScript for charts and live data.
"""

from flask import Blueprint, jsonify, request
from app.models.account import Account
from app.services.price_service import get_price_history
from app.services.portfolio_service import (
    get_combined_dashboard,
    get_portfolio_value_history,
    compute_holdings_for_account,
    enrich_holdings_with_prices,
)

api_bp = Blueprint("api", __name__)


@api_bp.route("/price_history")
def price_history():
    """
    Return historical price data for a single asset.

    Query params:
        symbol: Ticker or coin id.
        type: 'stock' or 'crypto'.
        period: '1W', '1M', '3M', '1Y'.

    Returns:
        JSON list of {date, price} objects.
    """
    symbol = request.args.get("symbol", "").strip()
    asset_type = request.args.get("type", "stock").strip()
    period = request.args.get("period", "1M").strip()

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    history = get_price_history(asset_type, symbol, period)
    return jsonify(history)


@api_bp.route("/portfolio_history")
def portfolio_history():
    """
    Return portfolio value over time series for the main chart.

    Query params:
        current_value (optional float): The already-computed live portfolio
            total value. When supplied the last chart point is replaced with
            this real market value. When omitted the series ends at the last
            cumulative deposit figure (safe default -- no price fetch needed).

    Returns:
        JSON list of {date, value} objects.
    """
    current_value = request.args.get("current_value", type=float)
    series = get_portfolio_value_history(current_total=current_value)
    return jsonify(series)


@api_bp.route("/dashboard_data")
def dashboard_data():
    """
    Return full dashboard data as JSON (for AJAX refresh).

    Returns:
        JSON dashboard object.
    """
    dashboard = get_combined_dashboard()
    return jsonify(dashboard)
