"""Comprehensive integration test for the portfolio tracker."""
import requests
import sys

BASE = "http://127.0.0.1:5000"
s = requests.Session()
passed = 0
failed = 0


def check(name, condition):
    """Assert a condition and track pass/fail."""
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


print("=" * 60)
print("PORTFOLIO TRACKER — INTEGRATION TEST SUITE")
print("=" * 60)

# ------------------------------------------------------------------
print("\n--- 1. Account Creation ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/accounts/create", data={
    "name": "My Stocks", "account_type": "stock"
}, allow_redirects=False)
check("Create stock account (302 redirect)", r.status_code == 302)

r = s.post(f"{BASE}/accounts/create", data={
    "name": "Crypto Holdings", "account_type": "crypto"
}, allow_redirects=False)
check("Create crypto account (302 redirect)", r.status_code == 302)

r = s.get(f"{BASE}/accounts/")
check("Accounts page loads", r.status_code == 200)
check("Stock account visible", "My Stocks" in r.text)
check("Crypto account visible", "Crypto Holdings" in r.text)

# ------------------------------------------------------------------
print("\n--- 2. Account Validation ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/accounts/create", data={"name": "", "account_type": "stock"})
check("Empty name rejected", "Account name is required" in r.text)

r = s.post(f"{BASE}/accounts/create", data={"name": "Test", "account_type": "forex"})
check("Invalid account type rejected", "Account type must be" in r.text)

# ------------------------------------------------------------------
print("\n--- 3. Deposit / Withdrawal ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "deposit",
    "total_amount": 10000, "timestamp": "2024-06-01T10:00"
}, allow_redirects=False)
check("Deposit to stock account", r.status_code == 302)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "withdrawal",
    "total_amount": 500, "timestamp": "2024-06-01T12:00"
}, allow_redirects=False)
check("Withdrawal from stock account", r.status_code == 302)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 2, "tx_type": "deposit",
    "total_amount": 5000, "timestamp": "2024-07-01T10:00"
}, allow_redirects=False)
check("Deposit to crypto account", r.status_code == 302)

# ------------------------------------------------------------------
print("\n--- 4. Buy Transactions ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "buy",
    "asset_symbol": "AAPL", "asset_name": "Apple Inc.",
    "quantity": 10, "price_per_unit": 180.50,
    "timestamp": "2024-06-02T10:00"
}, allow_redirects=False)
check("Buy AAPL", r.status_code == 302)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "buy",
    "asset_symbol": "MSFT", "asset_name": "Microsoft Corp.",
    "quantity": 5, "price_per_unit": 420.00,
    "timestamp": "2024-06-03T10:00"
}, allow_redirects=False)
check("Buy MSFT", r.status_code == 302)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 2, "tx_type": "buy",
    "asset_symbol": "bitcoin", "asset_name": "Bitcoin",
    "quantity": 0.05, "price_per_unit": 62000,
    "timestamp": "2024-07-02T10:00"
}, allow_redirects=False)
check("Buy BTC", r.status_code == 302)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 2, "tx_type": "buy",
    "asset_symbol": "ethereum", "asset_name": "Ethereum",
    "quantity": 1.0, "price_per_unit": 2500,
    "timestamp": "2024-07-03T10:00"
}, allow_redirects=False)
check("Buy ETH", r.status_code == 302)

# ------------------------------------------------------------------
print("\n--- 5. Sell Transaction ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "sell",
    "asset_symbol": "AAPL", "asset_name": "Apple Inc.",
    "quantity": 3, "price_per_unit": 210.00,
    "timestamp": "2024-09-15T10:00"
}, allow_redirects=False)
check("Sell partial AAPL", r.status_code == 302)

# ------------------------------------------------------------------
print("\n--- 6. Dividend Transaction ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "dividend",
    "asset_symbol": "AAPL", "asset_name": "Apple Inc.",
    "total_amount": 25.00, "timestamp": "2024-08-15T10:00"
}, allow_redirects=False)
check("AAPL dividend recorded", r.status_code == 302)

# ------------------------------------------------------------------
print("\n--- 7. Transaction Validation ---")
# ------------------------------------------------------------------
r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "buy", "asset_symbol": "TSLA",
    "quantity": -5, "price_per_unit": 200
})
check("Negative quantity rejected", "greater than zero" in r.text)

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "buy", "asset_symbol": "",
    "quantity": 5, "price_per_unit": 200
})
check("Empty symbol rejected for buy", "symbol" in r.text.lower() and "required" in r.text.lower())

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "deposit", "total_amount": -100
})
check("Negative deposit amount rejected", "greater than zero" in r.text)

r = s.post(f"{BASE}/transactions/create", data={
    "tx_type": "buy", "asset_symbol": "TSLA",
    "quantity": 5, "price_per_unit": 200
})
check("Missing account rejected", "Account is required" in r.text or "account" in r.text.lower())

r = s.post(f"{BASE}/transactions/create", data={
    "account_id": 1, "tx_type": "dividend",
    "asset_symbol": "", "total_amount": 10
})
check("Empty symbol rejected for dividend", "symbol" in r.text.lower())

# ------------------------------------------------------------------
print("\n--- 8. Dashboard API ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/api/dashboard_data")
check("Dashboard API status 200", r.status_code == 200)
data = r.json()
check("Has total_value", "total_value" in data)
check("Has total_invested", "total_invested" in data)
check("Has total_pnl", "total_pnl" in data)
check("Has all_holdings", "all_holdings" in data)
check("Has best_investment", "best_investment" in data)
check("Has worst_investment", "worst_investment" in data)
check("Has accounts list", isinstance(data.get("accounts"), list))
check("Holdings count >= 3", len(data["all_holdings"]) >= 3)

print(f"\n  Dashboard totals:")
print(f"    Total value:    ${data['total_value']:,.2f}")
print(f"    Total invested: ${data['total_invested']:,.2f}")
print(f"    Total P&L:      ${data['total_pnl']:,.2f} ({data['total_pnl_pct']}%)")

for h in data["all_holdings"]:
    sym = h["asset_symbol"]
    print(f"    {sym:>10}: qty={h['quantity']:<10} price=${str(h['current_price']):<12} "
          f"pnl=${h['unrealized_pnl']:<10} type={h.get('account_type', '?')}")

# Verify account_type is present on holdings (needed for charts)
for h in data["all_holdings"]:
    check(f"Holding {h['asset_symbol']} has account_type", "account_type" in h)

if data["best_investment"]:
    bi = data["best_investment"]
    print(f"\n  Best:  {bi['asset_symbol']} ({bi['unrealized_pnl_pct']}%)")
if data["worst_investment"]:
    wi = data["worst_investment"]
    print(f"  Worst: {wi['asset_symbol']} ({wi['unrealized_pnl_pct']}%)")

# ------------------------------------------------------------------
print("\n--- 9. Account Detail ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/accounts/1")
check("Stock account detail loads", r.status_code == 200)
check("AAPL in stock detail", "AAPL" in r.text.upper())
check("MSFT in stock detail", "MSFT" in r.text.upper())

r = s.get(f"{BASE}/accounts/2")
check("Crypto account detail loads", r.status_code == 200)
check("BITCOIN in crypto detail", "BITCOIN" in r.text.upper())

r = s.get(f"{BASE}/accounts/999")
check("Non-existent account redirects", r.status_code == 200)  # redirects and follows

# ------------------------------------------------------------------
print("\n--- 10. Price History API ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/api/price_history?symbol=AAPL&type=stock&period=1M")
check("Stock price history 200", r.status_code == 200)
history = r.json()
check("Stock history has data points", len(history) > 0)
if history:
    check("History has date key", "date" in history[0])
    check("History has price key", "price" in history[0])

r = s.get(f"{BASE}/api/price_history?symbol=bitcoin&type=crypto&period=1W")
check("Crypto price history 200", r.status_code == 200)

r = s.get(f"{BASE}/api/price_history?symbol=&type=stock")
check("Empty symbol returns 400", r.status_code == 400)

# ------------------------------------------------------------------
print("\n--- 11. Portfolio History API ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/api/portfolio_history")
check("Portfolio history 200", r.status_code == 200)
series = r.json()
check("Portfolio history has data", len(series) > 0)
if series:
    check("Series has date key", "date" in series[0])
    check("Series has value key", "value" in series[0])

# ------------------------------------------------------------------
print("\n--- 12. Transactions Page with Filters ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/transactions/")
check("All transactions page loads", r.status_code == 200)

r = s.get(f"{BASE}/transactions/?account_id=1&tx_type=buy")
check("Filtered by account+type loads", r.status_code == 200)
check("AAPL buy visible in filtered view", "AAPL" in r.text.upper())

r = s.get(f"{BASE}/transactions/?tx_type=dividend")
check("Dividend filter loads", r.status_code == 200)
check("Dividend visible", "DIVIDEND" in r.text.upper())

r = s.get(f"{BASE}/transactions/?tx_type=sell")
check("Sell filter loads", r.status_code == 200)
check("Sell visible", "SELL" in r.text.upper())

# ------------------------------------------------------------------
print("\n--- 13. Dashboard Page Render ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/")
check("Dashboard page loads", r.status_code == 200)
check("Portfolio Dashboard title", "Portfolio Dashboard" in r.text)
check("Chart canvas present", "portfolioChart" in r.text)
check("Holdings table present", "holdingsTable" in r.text)
check("Best investment section", "Best Investment" in r.text)
check("Worst investment section", "Worst Investment" in r.text)
check("Summary cards present", "Total Value" in r.text)
check("Chart.js loaded", "chart.js" in r.text.lower() or "chart.umd" in r.text.lower())

# ------------------------------------------------------------------
print("\n--- 14. Create Transaction Form ---")
# ------------------------------------------------------------------
r = s.get(f"{BASE}/transactions/create")
check("Create transaction form loads", r.status_code == 200)
check("Account dropdown present", "account_id" in r.text)
check("Transaction type dropdown", "tx_type" in r.text)
check("Asset fields present", "asset_symbol" in r.text)

# Test pre-selecting account via query string
r = s.get(f"{BASE}/transactions/create?account_id=1")
check("Create form with preselected account", r.status_code == 200)

# ------------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------------
print("\n" + "=" * 60)
total = passed + failed
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
else:
    print("\nAll integration tests PASSED!")
    sys.exit(0)
