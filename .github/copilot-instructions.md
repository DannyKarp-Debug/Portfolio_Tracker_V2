# Portfolio Tracker V2 — Copilot Instructions

## Project context and goals
- This is a Flask-based portfolio tracker for **stock and crypto** accounts.
- Users manage accounts/transactions, then view:
  - server-rendered dashboard/account pages
  - lazily hydrated live prices via `/api/dashboard_data`
  - chart/history data via `/api/*` endpoints
- Core goal: keep **portfolio math and state derivation** centralized in services, while routes stay thin and templates/JS focus on presentation.

## Architecture and design rules
- Keep existing layered structure:
  - `app/routes/*`: HTTP wiring + request parsing + response/flash/redirect
  - `app/services/*`: business logic (portfolio math, pricing, validation)
  - `app/models/*`: SQLAlchemy schema + serialization
  - `app/templates/*` + `app/static/js/*`: UI rendering and client-side behavior
- Use the app factory pattern in `app/__init__.py`; register new blueprints there.
- Preserve the current lazy-load strategy:
  - SSR uses `skip_prices=True`
  - frontend `prices.js` hydrates from `/api/dashboard_data` and caches in `sessionStorage`.
- Reuse existing dispatchers in `price_service.py`:
  - `PRICE_FETCHERS`
  - `HISTORY_FETCHERS`
  when adding new asset types/providers.
- Do not duplicate holdings/P&L/cost-basis logic in routes/templates/JS.

## Coding conventions
- Python:
  - snake_case, typed function signatures where already used, docstrings on service/route functions.
  - Prefer `db.session.get(Model, id)` for by-id lookups (existing pattern).
- Naming and normalization:
  - transaction/account types are lowercase (`crypto`, `stock`, `buy`, `sell`, etc.).
  - symbols are normalized at route/service boundaries (stock uppercase for provider calls, stored symbols often lowercase).
- Frontend JS:
  - keep plain vanilla JS style consistent with current files (`app/static/js/*.js`).
  - update DOM through existing data attributes and helper flow in `prices.js`.

## Error-handling expectations
- Follow repo behavior instead of introducing new global handlers:
  - HTML form/CRUD failures: flash message + redirect/re-render form.
  - API validation errors: explicit `400` JSON (`{"error": ...}`).
  - External market-data failures: degrade gracefully (`None`, `{}`, or `[]`) from services; UI should remain usable.
- Do not swallow validation failures; surface user-facing messages using existing flash/JSON patterns.

## Testing and validation workflow
- This repo currently has no dedicated lint/typecheck/test config committed (no `pytest`, `ruff`, `mypy`, etc.).
- Use existing validation pattern from the repo README:
  - `python -m compileall app config.py`
- For runtime smoke checks:
  - `python run.py`
  - manually verify: dashboard load, account CRUD, transaction CRUD, `/api/price_history`, `/api/dashboard_data`, `/api/portfolio_history`.

## File-change discipline
- Make surgical edits only in relevant files.
- Do not perform unrelated refactors, renames, formatting churn, or architecture rewrites.
- Keep route handlers thin; move non-trivial logic into `app/services/*`.
- If schema changes are required, keep migration logic centralized in `app/__init__.py` (current guarded runtime migration pattern).

## Dependency policy
- Prefer existing dependencies and internal helpers before adding packages.
- If a new dependency is necessary:
  - justify why existing `Flask`/`SQLAlchemy`/`requests`/`yfinance` stack is insufficient,
  - pin version in `requirements.txt`,
  - keep integration minimal and consistent with current architecture.

## Security and privacy guardrails
- Never commit secrets or tokens; use environment variables (`config.py` + `.env` via `python-dotenv`).
- Respect timeout/caching controls already in `Config` for outbound price requests.
- Validate and normalize all user input via `validation_service.py` (extend it instead of bypassing).
- Avoid exposing stack traces or internal exceptions to API/UI responses.

## How to add a new feature (checklist)
1. Identify boundary: route (`app/routes`) vs service (`app/services`) vs model (`app/models`) vs UI (`templates/js`).
2. Add/extend validation in `validation_service.py`.
3. Implement business logic in service layer (not in route/template JS).
4. Wire route endpoint and response style (HTML + flash/redirect, or JSON + status codes).
5. Update templates and JS if UI interaction changes.
6. If persistence changes are needed, update model + guarded migration in `app/__init__.py`.
7. Run `python -m compileall app config.py`.
8. Run manual smoke flow for impacted pages and `/api/*` endpoints.

## Communication and PR summary expectations
- Summarize:
  - what changed,
  - why it changed,
  - which files/modules were touched,
  - validation performed (compileall + manual flows),
  - any known limitations/follow-ups.
- Call out any behavior changes explicitly (especially pricing, portfolio math, validation, or schema behavior).
