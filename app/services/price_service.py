"""
Price fetching service.

Handles live and historical price retrieval for both stocks/ETFs (via yfinance)
and cryptocurrencies (via CoinGecko public API).

Adding a new asset type requires only adding a new fetcher function pair here
and registering it in the dispatcher dictionaries at the bottom.
"""

from datetime import datetime, timezone
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import yfinance as yf
from config import Config


# Maximum retry attempts for rate-limited yfinance requests
_YF_MAX_RETRIES = 3
_YF_RETRY_DELAY = 1  # seconds, doubles each attempt

_DEFAULT_TIMEOUT = Config.PRICE_REQUEST_TIMEOUT_SECONDS
_PRICE_CACHE_TTL = Config.PRICE_CACHE_TTL_SECONDS
_FINNHUB_KEY = Config.FINNHUB_API_KEY
_FINNHUB_BASE = "https://finnhub.io/api/v1"
_YAHOO_CHART_BASE = "https://query2.finance.yahoo.com/v8/finance/chart"
_STOOQ_BASE = "https://stooq.com/q/l/"
_MAX_BULK_WORKERS = 8
_price_cache: dict[str, tuple[float, float]] = {}
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json,text/csv,*/*",
}


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
    cache_key = f"stock:{symbol}"
    cached_price = _cache_get(cache_key)
    if cached_price is not None:
        return cached_price

    price = _fetch_stock_price_no_cache(symbol)
    if price is not None:
        _cache_set(cache_key, price)
        return price

    return _cache_get(cache_key, allow_stale=True)


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


def _cache_get(key: str, allow_stale: bool = False) -> float | None:
    cached = _price_cache.get(key)
    if not cached:
        return None
    price, ts = cached
    if allow_stale or (time.time() - ts) <= _PRICE_CACHE_TTL:
        return float(price)
    return None


def _cache_set(key: str, price: float) -> None:
    _price_cache[key] = (float(price), time.time())


def _normalize_stock_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _to_stooq_symbol(symbol: str) -> str:
    s = symbol.strip().lower()
    known_exchange_suffixes = {
        "us", "de", "uk", "pl", "to", "v", "ax", "hk", "jp", "fr", "it", "es",
    }
    if "." not in s:
        return f"{s}.us"
    _, right = s.rsplit(".", 1)
    if right in known_exchange_suffixes:
        return s
    return f"{s.replace('.', '-')}.us"


def _fetch_stock_price_no_cache(symbol: str) -> float | None:
    for fetcher in (
        _fetch_stock_price_finnhub,
        _fetch_stock_price_stooq,
        _fetch_stock_price_yahoo_chart,
        _fetch_stock_price_yfinance,
    ):
        price = fetcher(symbol)
        if price is not None:
            return price
    return None


def _fetch_stock_price_finnhub(symbol: str) -> float | None:
    if not _FINNHUB_KEY:
        return None
    try:
        resp = requests.get(
            f"{_FINNHUB_BASE}/quote",
            params={"symbol": symbol, "token": _FINNHUB_KEY},
            headers=_DEFAULT_HEADERS,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Finnhub's "c" is current price.
        price = data.get("c")
        if price is None:
            return None
        price_f = float(price)
        return price_f if price_f > 0 else None
    except Exception:
        return None


def _fetch_stock_price_stooq(symbol: str) -> float | None:
    try:
        resp = requests.get(
            _STOOQ_BASE,
            params={"s": _to_stooq_symbol(symbol), "i": "d"},
            headers=_DEFAULT_HEADERS,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        rows = [line.strip() for line in resp.text.splitlines() if line.strip()]
        if len(rows) < 2:
            return None
        values = [part.strip() for part in rows[1].split(",")]
        if len(values) < 7:
            return None
        close = values[6]
        if not close or close.lower() in {"n/d", "null"}:
            return None
        price = float(close)
        return price if price > 0 else None
    except Exception:
        return None


def _fetch_stock_price_yahoo_chart(symbol: str) -> float | None:
    try:
        resp = requests.get(
            f"{_YAHOO_CHART_BASE}/{symbol}",
            params={"range": "5d", "interval": "1d"},
            headers=_DEFAULT_HEADERS,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("chart", {}).get("result", [])
        if not results:
            return None
        closes = (
            results[0]
            .get("indicators", {})
            .get("quote", [{}])[0]
            .get("close", [])
        )
        for value in reversed(closes):
            if value is None:
                 continue
            price = float(value)
            if price > 0:
                return price
        return None
    except Exception:
        return None


def _fetch_stock_price_yfinance(symbol: str) -> float | None:
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

    normalized_to_original: dict[str, str] = {}
    for original in symbols:
        normalized = _normalize_stock_symbol(original)
        if normalized:
            normalized_to_original[normalized] = original

    if not normalized_to_original:
        return {}

    result: dict[str, float] = {}
    unresolved: list[str] = []

    for normalized, original in normalized_to_original.items():
        cached = _cache_get(f"stock:{normalized}")
        if cached is not None:
            result[original] = cached
        else:
            unresolved.append(normalized)

    if unresolved:
        max_workers = min(_MAX_BULK_WORKERS, len(unresolved))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(_fetch_stock_price_no_cache, normalized): normalized
                for normalized in unresolved
            }
            for future in as_completed(future_map):
                normalized = future_map[future]
                original = normalized_to_original[normalized]
                try:
                    price = future.result()
                except Exception:
                    price = None
                if price is not None:
                    _cache_set(f"stock:{normalized}", price)
                    result[original] = price

    if len(result) < len(normalized_to_original):
        for normalized, original in normalized_to_original.items():
            if original in result:
                continue
            stale = _cache_get(f"stock:{normalized}", allow_stale=True)
            if stale is not None:
                result[original] = stale

    return result


def _fetch_bulk_stock_prices_fallback(symbols: list[str]) -> dict[str, float]:
    """Individual per-ticker fallback when bulk download fails."""
    prices = {}
    for sym in symbols:
        p = fetch_stock_price(sym)
        if p is not None:
            prices[sym] = p
    return prices
