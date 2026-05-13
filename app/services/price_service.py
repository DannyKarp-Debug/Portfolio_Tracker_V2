"""
Price fetching service.

Handles live and historical price retrieval for both stocks/ETFs (via yfinance)
and cryptocurrencies (via CoinGecko public API).

Adding a new asset type requires only adding a new fetcher function pair here
and registering it in the dispatcher dictionaries at the bottom.
"""

from datetime import datetime, timedelta, timezone
import time
import requests
import yfinance as yf
from config import Config


# Maximum retry attempts for rate-limited yfinance requests
_YF_MAX_RETRIES = 3
_YF_RETRY_DELAY = 2  # seconds, doubles each attempt


# ---------------------------------------------------------------------------
# Stock / ETF prices
# ---------------------------------------------------------------------------

def fetch_stock_price(symbol: str) -> float | None:
    """
    Fetch the latest market price for a stock or ETF ticker.

    Includes retry logic with exponential backoff to handle
    Yahoo Finance rate limiting.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL', 'SPY').

    Returns:
        Current price as a float, or None if unavailable.
    """
    symbol = symbol.upper()
    delay = _YF_RETRY_DELAY
    for attempt in range(_YF_MAX_RETRIES):
        try:
            ticker = yf.Ticker(symbol)
            try:
                info = ticker.fast_info
                price = getattr(info, "last_price", None)
            except Exception:
                price = None
            if price is None:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price:
                return float(price)
        except Exception as exc:
            if "rate" in str(exc).lower() and attempt < _YF_MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return None
    return None


def fetch_stock_history(symbol: str, period: str = "1mo") -> list[dict]:
    """
    Fetch historical daily closing prices for a stock or ETF.

    Includes retry logic for rate-limiting resilience.

    Args:
        symbol: Ticker symbol.
        period: yfinance period string — '7d', '1mo', '3mo', '1y'.

    Returns:
        List of dicts with 'date' (ISO string) and 'price' keys.
    """
    period_map = {"1W": "7d", "1M": "1mo", "3M": "3mo", "1Y": "1y"}
    yf_period = period_map.get(period, period)
    symbol = symbol.upper()
    delay = _YF_RETRY_DELAY
    for attempt in range(_YF_MAX_RETRIES):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=yf_period)
            result = []
            for date, row in hist.iterrows():
                result.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "price": round(float(row["Close"]), 4),
                })
            return result
        except Exception as exc:
            if "rate" in str(exc).lower() and attempt < _YF_MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return []
    return []


# ---------------------------------------------------------------------------
# Crypto prices (CoinGecko)
# ---------------------------------------------------------------------------

COINGECKO_BASE = Config.COINGECKO_BASE_URL


def fetch_crypto_price(coin_id: str) -> float | None:
    """
    Fetch the current USD price for a cryptocurrency from CoinGecko.

    Args:
        coin_id: CoinGecko coin identifier (e.g. 'bitcoin', 'ethereum').

    Returns:
        Current price as a float, or None on failure.
    """
    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data[coin_id]["usd"])
    except Exception:
        return None


def fetch_crypto_history(coin_id: str, period: str = "1M") -> list[dict]:
    """
    Fetch historical daily prices for a cryptocurrency from CoinGecko.

    Args:
        coin_id: CoinGecko coin identifier.
        period: '1W', '1M', '3M', or '1Y'.

    Returns:
        List of dicts with 'date' (ISO string) and 'price' keys.
    """
    days_map = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    days = days_map.get(period, 30)
    try:
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = []
        for timestamp_ms, price in data.get("prices", []):
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            result.append({
                "date": dt.strftime("%Y-%m-%d"),
                "price": round(price, 4),
            })
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Dispatchers — the single place to register new asset types
# ---------------------------------------------------------------------------

PRICE_FETCHERS: dict[str, callable] = {
    "stock": fetch_stock_price,
    "crypto": fetch_crypto_price,
}

HISTORY_FETCHERS: dict[str, callable] = {
    "stock": fetch_stock_history,
    "crypto": fetch_crypto_history,
}


def get_current_price(asset_type: str, symbol: str) -> float | None:
    """
    Dispatch to the correct price fetcher based on asset type.

    Args:
        asset_type: 'stock' or 'crypto'.
        symbol: Ticker or coin id.

    Returns:
        Current price or None.
    """
    fetcher = PRICE_FETCHERS.get(asset_type)
    if fetcher is None:
        return None
    return fetcher(symbol)


def get_price_history(asset_type: str, symbol: str, period: str = "1M") -> list[dict]:
    """
    Dispatch to the correct history fetcher based on asset type.

    Args:
        asset_type: 'stock' or 'crypto'.
        symbol: Ticker or coin id.
        period: Time range string.

    Returns:
        List of date/price dicts.
    """
    fetcher = HISTORY_FETCHERS.get(asset_type)
    if fetcher is None:
        return []
    return fetcher(symbol, period)


def fetch_bulk_crypto_prices(coin_ids: list[str]) -> dict[str, float]:
    """
    Fetch current USD prices for multiple cryptocurrencies in a single request.

    Args:
        coin_ids: List of CoinGecko coin identifiers.

    Returns:
        Dict mapping coin_id to price.
    """
    if not coin_ids:
        return {}
    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": ",".join(coin_ids), "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {cid: float(data[cid]["usd"]) for cid in data}
    except Exception:
        return {}


def fetch_bulk_stock_prices(symbols: list[str]) -> dict[str, float]:
    """
    Fetch current prices for multiple stock tickers.

    Uses the original (possibly lowercase) symbol as the dict key so it
    matches the holdings data, while passing the uppercased version to
    yfinance.

    Args:
        symbols: List of ticker symbols.

    Returns:
        Dict mapping original symbol to price.
    """
    prices = {}
    for sym in symbols:
        p = fetch_stock_price(sym)
        if p is not None:
            prices[sym] = p
    return prices
