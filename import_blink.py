"""
One-time script: import transactions.json into the Blink account.
Run from the project root: python import_blink.py
"""

import json
from datetime import datetime, timezone
from app import create_app, db
from app.models.account import Account
from app.models.transaction import Transaction

app = create_app()

with app.app_context():
    # Find the Blink account (case-insensitive)
    account = Account.query.filter(
        Account.name.ilike("blink")
    ).first()

    if not account:
        print("ERROR: No account named 'Blink' found. Existing accounts:")
        for a in Account.query.all():
            print(f"  - {a.name} (id={a.id})")
        exit(1)

    print(f"Found account: '{account.name}' (id={account.id}, type={account.account_type})")

    with open("transactions.json", "r") as f:
        data = json.load(f)

    type_map = {"buy": "buy", "sell": "sell", "dividend": "dividend"}
    inserted = 0
    skipped = 0

    for row in data:
        tx_type = row["type"].strip().lower()
        if tx_type not in type_map:
            print(f"  SKIP unknown type: {row['type']}")
            skipped += 1
            continue

        symbol = (row.get("symbol") or "").strip().lower() or None
        qty = float(row.get("quantity") or 0)
        price = float(row.get("price") or 0)
        amount = float(row.get("amount") or 0)
        date_str = row.get("date", "").strip()

        try:
            ts = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        if tx_type in ("buy", "sell"):
            quantity = qty if qty else None
            price_per_unit = price if price else None
            total_amount = amount
        else:
            # dividend
            quantity = None
            price_per_unit = None
            total_amount = amount

        tx = Transaction(
            account_id=account.id,
            tx_type=tx_type,
            asset_symbol=symbol,
            asset_name=symbol.upper() if symbol else None,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_amount=total_amount,
            timestamp=ts,
            notes=None,
        )
        db.session.add(tx)
        inserted += 1
        print(f"  + {date_str} {tx_type.upper():10} {(symbol or '').upper():6}  ${amount:>10,.2f}")

    db.session.commit()
    print(f"\nDone! Inserted {inserted} transactions ({skipped} skipped).")
