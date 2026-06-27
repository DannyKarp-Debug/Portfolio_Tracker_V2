# LLM Context Spec — Portfolio_Tracker_V2

## 1. CORE SPECIFICATION & COMPLIANCE MATRIX

### Runtime, Language, & Framework Versions

| Component | Version Spec | Source |
|---|---|---|
| Python runtime | Not pinned in repo; target `>=3.11` | project convention |
| Flask | `3.1.1` | `requirements.txt` |
| SQLAlchemy | `2.0.41` | `requirements.txt` |
| Flask-SQLAlchemy | `3.1.1` | `requirements.txt` |
| requests | `2.32.3` | `requirements.txt` |
| yfinance | `0.2.55` | `requirements.txt` |
| python-dotenv | `1.1.0` | `requirements.txt` |
| Chart.js (CDN) | `4.4.7` | `app/templates/base.html` |

### Primary Dependencies (Behavior-Critical)

- `Flask`: routing, request/response lifecycle, template rendering.
- `Flask-SQLAlchemy` + `SQLAlchemy`: ORM, schema mapping, persistence.
- `requests`: external HTTP market-data calls.
- `yfinance`: stock history + fallback stock quote source.
- `python-dotenv`: env injection into runtime config.
- `Chart.js`: portfolio and asset history visualization.

### Data Layer

| Layer | Implementation | Location |
|---|---|---|
| Primary DB | SQLite (`sqlite:///portfolio.db`) | `config.py`, `instance/portfolio.db` |
| ORM | SQLAlchemy models (`Account`, `Transaction`) | `app/models/*.py` |
| Migration mechanism | Runtime schema patch (`fee` column) | `app/__init__.py::_migrate_add_fee_column` |
| Server-side cache | In-process dict TTL cache for stock prices | `app/services/price_service.py` (`_price_cache`) |
| Client-side cache | `sessionStorage` dashboard payload TTL cache | `app/static/js/prices.js` |

---

## 2. SYSTEM BOUNDARIES & REPOSITORY GEOMETRY

### Architectural Pattern

- **Modular monolith**
- **Service-layer architecture**
- **MVC-style server-rendered web app (Flask + Jinja)**
- **Hybrid render strategy**: SSR placeholders + async price hydration

### Directory Tree Graph (Critical Surface Only)

```text
/
├─ run.py                                  # process entrypoint
├─ config.py                               # env-backed configuration
├─ requirements.txt
├─ import_blink.py                         # one-off data import script
├─ app/
│  ├─ __init__.py                          # app factory, blueprint registration, db init
│  ├─ models/
│  │  ├─ account.py
│  │  ├─ transaction.py
│  │  └─ __init__.py
│  ├─ routes/
│  │  ├─ dashboard.py                      # GET /
│  │  ├─ accounts.py                       # /accounts/*
│  │  ├─ transactions.py                   # /transactions/*
│  │  └─ api.py                            # /api/*
│  ├─ services/
│  │  ├─ portfolio_service.py              # holdings/pnl aggregation
│  │  ├─ price_service.py                  # market data providers
│  │  └─ validation_service.py             # input validation rules
│  ├─ templates/
│  │  ├─ base.html
│  │  ├─ dashboard.html
│  │  ├─ account_detail.html
│  │  ├─ accounts.html
│  │  ├─ create_transaction.html
│  │  ├─ edit_transaction.html
│  │  └─ transactions.html
│  └─ static/
│     ├─ css/style.css
│     └─ js/{app,prices,charts,sort,transaction_form}.js
└─ instance/portfolio.db
```

### Deterministic Data Flow (Mutation/Request Pipeline)

**Example A — Dashboard hydration path**
1. Ingress: `GET /` -> `app/routes/dashboard.py:index`.
2. Route calls `get_combined_dashboard(skip_prices=True)` in `portfolio_service`.
3. Jinja renders placeholders (`dashboard.html`).
4. Client `prices.js` calls `GET /api/dashboard_data`.
5. `app/routes/api.py:dashboard_data` calls `get_combined_dashboard(skip_prices=False)`.
6. `portfolio_service` calls bulk price fetchers in `price_service`.
7. `price_service` retrieves/cache-resolves market prices, returns dicts.
8. Service computes totals/P&L/weights, API returns JSON.
9. Client patches DOM + triggers `loadPortfolioChart` in `charts.js`.

**Example B — Transaction create path**
1. Ingress: `POST /transactions/create` -> `transactions.py:create_transaction`.
2. Form payload normalized to `data` dict.
3. `validate_transaction_data(data)` in `validation_service`.
4. Route computes derived values (`total_amount`, `fee`, parsed `timestamp`).
5. `Transaction(...)` instantiated and persisted via `db.session.add/commit`.
6. Redirect to `/transactions` with flash status.

---

## 3. VECTOR & SEMANTIC FEATURE MAPPING (SOURCE OF TRUTH)

### Ingress/Routing

[App Factory + Blueprint Wiring] -> `app/__init__.py`  
[Root Dashboard Route] -> `app/routes/dashboard.py`  
[Accounts HTTP Surface] -> `app/routes/accounts.py`  
[Transactions HTTP Surface] -> `app/routes/transactions.py`  
[JSON API Surface] -> `app/routes/api.py`  
[Entrypoint] -> `run.py`

### Authentication & Authorization

[AuthN/AuthZ Implementation] -> **Not implemented in repository**  
[Session/RBAC/ABAC] -> **Not implemented**  
[Implication] -> All routes are effectively local-open; no user boundary.

### State Management, Schemas & Type Definitions

[Account Schema] -> `app/models/account.py`  
[Transaction Schema] -> `app/models/transaction.py`  
[Model Export Boundary] -> `app/models/__init__.py`  
[Config + Env State] -> `config.py`  
[Runtime Migration Patch] -> `app/__init__.py::_migrate_add_fee_column`  
[Portfolio Derived State Logic] -> `app/services/portfolio_service.py`  
[Validation Rule Set] -> `app/services/validation_service.py`  
[Client Price State Cache] -> `app/static/js/prices.js` (`sessionStorage`)

### Side Effects & Async Ingress

[External Market HTTP Calls] -> `app/services/price_service.py`  
[DB Mutation Side Effects] -> `app/routes/accounts.py`, `app/routes/transactions.py`  
[Async Client Fetch Loop] -> `app/static/js/prices.js`, `app/static/js/charts.js`  
[Background Workers/Queues/Cron] -> **Not implemented**  
[One-off Import Script] -> `import_blink.py`

---

## 4. ARCHITECTURAL CONSTRAINTS & COMPLIANCE INSTRUCTIONS

### Coding Paradigms (Required)

1. Keep route handlers thin; place business logic in `app/services/*`.
2. Keep persistence through SQLAlchemy models/session only.
3. Reuse existing service dispatch boundaries:
   - price dispatch: `PRICE_FETCHERS`, `HISTORY_FETCHERS`
   - validation via `validation_service`.
4. Preserve lazy price hydration model (`skip_prices=True` SSR + `/api/dashboard_data` async fill).

### Anti-Patterns to Avoid (Repository-Specific)

1. Do not duplicate holdings/P&L/cost-basis calculations in routes/templates/JS.
2. Do not add provider-specific quote logic outside `price_service.py`.
3. Do not bypass `validation_service` for transaction/account create workflows.
4. Do not introduce hardcoded schema rewrites in random modules; keep migration logic centralized.
5. Do not switch symbol casing conventions ad hoc (storage lowercase, display uppercase).

### Error Handling Contract

- Market/provider failures: return `None` or empty list/dict (graceful degradation), never hard-crash UI route.
- API validation failure: return explicit `400` JSON error where applicable (`/api/price_history`).
- CRUD route failures: flash user-facing error + redirect.
- Avoid broad exception leakage to templates; contain provider errors in service layer.

### Naming & Structure Conventions

- Python: `snake_case` for functions/variables, module names by domain.
- Blueprints: `*_bp` naming in route modules.
- Models: singular class names, plural SQL table names (`accounts`, `transactions`).
- JS: feature-based files in `app/static/js/`.
- Templates: page-level Jinja files in `app/templates/`; extend `base.html`.
- New domain behavior placement:
  - routes -> `app/routes/`
  - business logic -> `app/services/`
  - persistence schema -> `app/models/`
  - UI behavior -> `app/static/js/`, `app/templates/`

---

## 5. DETERMINISTIC CODE MODIFICATION PIPELINES (PSEUDO-ALGORITHMS)

### Pipeline A — Append a New API Endpoint/Route

```text
INPUT: new endpoint requirement
1) Select ingress surface:
   - HTML route -> app/routes/{domain}.py
   - JSON API -> app/routes/api.py (or new route module)
2) Define handler signature + route decorator.
3) If non-trivial logic exists:
   - create/extend function in app/services/{domain}_service.py
   - call service from route.
4) Validate inputs:
   - reuse app/services/validation_service.py or add targeted validator.
5) Build response:
   - HTML: render_template(...)
   - API: jsonify(...)
6) If new blueprint created:
   - register in app/__init__.py with url_prefix.
7) If UI needs it:
   - wire fetch/link/form in app/templates/* + app/static/js/*.
8) Run syntax validation: python -m compileall app config.py
OUTPUT: endpoint integrated across routing + service + UI (if required)
```

### Pipeline B — Append a New Database Entity/Migration

```text
INPUT: new persistent entity or schema change
1) Create model file in app/models/{entity}.py with db.Model mapping.
2) Export model in app/models/__init__.py.
3) Add relationships/foreign keys in involved models.
4) Handle schema evolution:
   - current repo pattern: runtime patch in app/__init__.py
   - implement guarded ALTER logic similar to _migrate_add_fee_column
5) Add service-layer operations in app/services/*.
6) Add route-level CRUD integration in app/routes/*.
7) Add/adjust templates and JS for create/read/update/delete flows.
8) Validate with python -m compileall app config.py and manual CRUD smoke.
OUTPUT: entity + migration path + app integration
```

### Pipeline C — Append a New UI Component/Frontend View

```text
INPUT: new page/component interaction
1) Add/update Jinja template under app/templates/.
2) Ensure base inheritance:
   - extends base.html
   - uses block content/head_extra/scripts
3) Add route to render template in app/routes/{domain}.py.
4) Add JS behavior in app/static/js/{feature}.js (or extend existing feature file).
5) Add CSS rules in app/static/css/style.css.
6) If component consumes live data:
   - add API endpoint in app/routes/api.py
   - implement service logic in app/services/*
   - fetch from JS and patch DOM deterministically.
7) Verify no duplication of portfolio math in frontend; keep computations server-side.
8) Validate syntax + manual render path.
OUTPUT: SSR view + optional async data path + style/behavior cohesion
```

