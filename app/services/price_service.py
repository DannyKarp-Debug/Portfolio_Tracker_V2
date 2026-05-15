"""
Price fetching service.

Handles live and historical price retrieval for both stocks/ETFs (via yfinance)
and cryptocurrencies (via CoinGecko public API).

Adding a new asset type requires only adding a new fetcher function pair here
and registering it in the dispatcher dictionaries at the bottom.
"""

from datetime import datetime, timezone
import time
import requests
import yfinance as yf
from config import Config


# Maximum retry attempts for rate-limited yfinance requests
_YF_MAX_RETRIES = 3
_YF_RETRY_DELAY = 1  # seconds, doubles each attempt


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
        period: yfinance period string -- '7d', '1mo', '3mo', '1y'.

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

# Map common short tickers to their CoinGecko coin IDs.
# CoinGecko uses full slugs (e.g. "bitcoin"), not exchange tickers (e.g. "btc").
COINGECKO_ID_MAP: dict[str, str] = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "usdt": "tether",
    "bnb": "binancecoin",
    "usdc": "usd-coin",
    "xrp": "ripple",
    "ada": "cardano",
    "avax": "avalanche-2",
    "doge": "dogecoin",
    "dot": "polkadot",
    "matic": "matic-network",
    "pol": "matic-network",
    "shib": "shiba-inu",
    "link": "chainlink",
    "uni": "uniswap",
    "ltc": "litecoin",
    "bch": "bitcoin-cash",
    "xlm": "stellar",
    "algo": "algorand",
    "etc": "ethereum-classic",
    "atom": "cosmos",
    "vet": "vechain",
    "near": "near",
    "ftm": "fantom",
    "mana": "decentraland",
    "sand": "the-sandbox",
    "ape": "apecoin",
    "xmr": "monero",
    "icp": "internet-computer",
    "fil": "filecoin",
    "trx": "tron",
    "dai": "dai",
    "xtz": "tezos",
    "theta": "theta-token",
    "hbar": "hedera-hashgraph",
    "mkr": "maker",
    "aave": "aave",
    "sushi": "sushi",
    "crv": "curve-dao-token",
    "comp": "compound-governance-token",
    "grt": "the-graph",
    "op": "optimism",
    "arb": "arbitrum",
    "sui": "sui",
    "apt": "aptos",
    "pepe": "pepe",
    "wbtc": "wrapped-bitcoin",
    "steth": "staked-ether",
    "leo": "leo-token",
    "ton": "the-open-network",
    "inj": "injective-protocol",
    "sei": "sei-network",
    "tia": "celestia",
    "jup": "jupiter-exchange-solana",
}


def _coingecko_id(symbol: str) -> str:
    """
    Resolve a crypto symbol or ticker to a CoinGecko coin ID.

    Falls back to the lowercased symbol itself if no mapping is found
    (handles cases where the full CoinGecko ID is already stored).

    Args:
        symbol: Raw symbol as stored in the database.

    Returns:
        CoinGecko coin ID string.
    """
    return COINGECKO_ID_MAP.get(symbol.lower(), symbol.lower())


def fetch_crypto_price(coin_id: str) -> float | None:
    """
    Fetch the current USD price for a cryptocurrency from CoinGecko.

    Args:
        coin_id: CoinGecko coin identifier or common ticker (e.g. 'bitcoin',
            'ethereum', 'btc', 'eth').

    Returns:
        Current price as a float, or None on failure.
    """
    resolved = _coingecko_id(coin_id)
    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": resolved, "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data[resolved]["usd"])
    except Exception:
        return None


def fetch_crypto_history(coin_id: str, period: str = "1M") -> list[dict]:
    """
    Fetch historical daily prices for a cryptocurrency from CoinGecko.

    Args:
        coin_id: CoinGecko coin identifier or common ticker.
        period: '1W', '1M', '3M', or '1Y'.

    Returns:
        List of dicts with 'date' (ISO string) and 'price' keys.
    """
    days_map = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    days = days_map.get(period, 30)
    resolved = _coingecko_id(coin_id)
    try:
        url = f"{COINGECKO_BASE}/coins/{resolved}/market_chart"
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
# Dispatchers -- the single place to register new asset types
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

    Resolves short tickers (e.g. 'btc') to CoinGecko IDs ('bitcoin') before
    calling the API, then maps the results back to the original symbols so
    callers can look up prices using whatever symbol is stored in the database.

    Args:
        coin_ids: List of CoinGecko coin identifiers or common tickers.

    Returns:
        Dict mapping original symbol (as passed in) to price.
    """
    if not coin_ids:
        return {}

    # Build resolved ID -> original symbol mapping (deduplicate resolved IDs)
    resolved_to_original: dict[str, str] = {}
    for sym in coin_ids:
        resolved = _coingecko_id(sym)
        resolved_to_original[resolved] = sym  # last writer wins for collisions

    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": ",".join(resolved_to_original.keys()), "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Map resolved IDs back to the original symbols callers expect
        return {
            resolved_to_original[cg_id]: float(price_data["usd"])
            for cg_id, price_data in data.items()
            if cg_id in resolved_to_original
        }
    except Exception:
        return {}


def fetch_bulk_stock_prices(symbols: list[str]) -> dict[str, float]:
    """
    Fetch current prices for multiple stock tickers in a single request.

    Uses yf.download() to batch all symbols into one HTTP call, avoiding
    per-ticker rate limiting. Falls back to individual fetches if the bulk
    call fails. Keys in the returned dict use the original (possibly
    lowercase) symbol so they match the holdings data.

    Args:
        symbols: List of ticker symbols.

    Returns:
        Dict mapping original symbol to price.
    """
    if not symbols:
        return {}

    # Map uppercase ticker -> original symbol (preserves caller casing)
    sym_map = {s.upper(): s for s in symbols}
    upper_syms = list(sym_map.keys())

    try:
        if len(upper_syms) == 1:
            df = yf.download(
                upper_syms[0], period="5d", auto_adjust=True,
                progress=False, multi_level_index=False,
            )
            if df.empty:
                return _fetch_bulk_stock_prices_fallback(symbols)
            close = df["Close"].dropna()
            if close.empty:
                return _fetch_bulk_stock_prices_fallback(symbols)
            return {sym_map[upper_syms[0]]: float(close.iloc[-1])}

        df = yf.download(
            upper_syms, period="5d", auto_adjust=True,
            progress=False,
        )
        if df.empty:
            return _fetch_bulk_stock_prices_fallback(symbols)

        # df["Close"] is a DataFrame with one column per ticker
        close_df = df["Close"]
        result = {}
        for sym_upper in upper_syms:
            if sym_upper in close_df.columns:
                col = close_df[sym_upper].dropna()
                if not col.empty:
                    result[sym_map[sym_upper]] = float(col.iloc[-1])
        return result if result else _fetch_bulk_stock_prices_fallback(symbols)

    except Exception:
        return _fetch_bulk_stock_prices_fallback(symbols)


def _fetch_bulk_stock_prices_fallback(symbols: list[str]) -> dict[str, float]:
    """Individual per-ticker fallback when bulk download fails."""
    prices = {}
    for sym in symbols:
        p = fetch_stock_price(sym)
        if p is not None:
            prices[sym] = p
    return prices
