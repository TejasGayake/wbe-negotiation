# N8N Hiring – Negotiation

**Wissen Baum Engineering Solutions** · Phase 1: data collection, candidate list, profitability & leverage summary, Excel export.

Flask (app factory + blueprints) · MySQL (PyMySQL) · Bootstrap 5 · Chart.js (summary page only) · openpyxl · Gunicorn.
Light theme only. All timestamps are IST (`Asia/Kolkata`). Money is shown with Indian grouping (₹12,34,567.00).

> Phase 1 does **not** include AI negotiation-script generation. `ng_5_negotiation_results` exists but is unused.

---

## 1. Project layout

```
wbe_negotiation/
├── app/
│   ├── __init__.py            # create_app(): extensions, blueprints, filters, errors, logging
│   ├── extensions.py          # db, migrate, csrf, compress, login_manager
│   ├── mappings.py            # ONE module for every TINYINT label <-> integer map + the status list
│   ├── services.py            # build_candidates_query, profitability, candidate_code, spider data, save, workflow
│   ├── cli.py                 # flask seed-admin
│   ├── models/                # one file per table (ng_1 … ng_6)
│   ├── forms/                 # auth.py, candidate.py, negotiation.py, fields.py
│   ├── blueprints/            # auth, dashboard, candidates, export, insights, negotiations
│   ├── utils/                 # timeutil.py (IST), formatting.py (Indian grouping)
│   ├── templates/             # base, auth, dashboard, candidates/*, insights, negotiations/*
│   └── static/                # css/app.css, js/app.js, img/favicon.svg
├── migrations/                # Flask-Migrate (0001 = exact schema, 0002 = negotiation workflow)
├── deploy/nginx.conf.example
├── tests/test_app.py          # 56 acceptance/smoke tests (SQLite, no MySQL needed)
├── config.py  wsgi.py  gunicorn.conf.py  requirements.txt  .env.example
```

---

## 2. Setup

Requires Python 3.11+ (uses `zoneinfo`) and a MySQL 8 / MariaDB 10.6+ database.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

On Windows / minimal images install tzdata if `zoneinfo` cannot find `Asia/Kolkata`: `pip install tzdata`.

> **Schema change (2026-10):** the status enum is now `Draft / InProcess / Generated / Closed` and
> `ng_6_negotiations` exists. Run `flask db upgrade` — migration `0002_negotiation_flow` rewrites the
> enum, maps the old `Ready` rows to `Draft` and creates the new table.

### 2.1 Create the database

```sql
CREATE DATABASE WARS CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wbe_user'@'%' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON WARS.* TO 'wbe_user'@'%';
FLUSH PRIVILEGES;
```

### 2.2 Configure `.env`

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
```

| Key | Meaning |
|---|---|
| `FLASK_ENV` | `Development` or `Production` (Production enables `SESSION_COOKIE_SECURE`) |
| `SECRET_KEY` | long random string |
| `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` | MySQL connection |
| `DB_SSL_CA` | optional path to a CA certificate to enable SSL to a remote MySQL |
| `ADMIN_NAME` `ADMIN_EMAIL` `ADMIN_PASSWORD` | used by `flask seed-admin` (prompted if missing) |

> `SESSION_COOKIE_SECURE=True` in Production means the site must be served over **HTTPS**, otherwise login cookies are not sent.

### 2.3 Run migrations

```bash
flask db upgrade
```

The initial migration (`migrations/versions/0001_initial_schema.py`) creates `ng_1_users`, `ng_2_candidates`,
`ng_3_client_details`, `ng_4_candidate_evaluation`, `ng_5_negotiation_results` with utf8mb4 / `utf8mb4_unicode_ci`,
signed `TINYINT` columns (needed for `-1`), the `status` ENUM, unique keys, indexes and `ON DELETE CASCADE` foreign keys.
No database views are used.

### 2.4 Create the first Admin

```bash
flask seed-admin            # reads ADMIN_* from .env, otherwise prompts
flask seed-admin --force    # create another Admin even if one exists
```

It refuses to run when an Admin already exists unless `--force` is given. Credentials are never hard-coded.
Additional HR users can be inserted with the same model (`role='HR'`) from a Flask shell:

```python
flask shell
>>> from app.models import User; from app.extensions import db
>>> u = User(name="Hira", email="hira@company.com", role="HR", is_active=1); u.set_password("a-strong-pass"); db.session.add(u); db.session.commit()
```

---

## 3. Run

**Development**

```bash
flask --app wsgi run --debug
```

Runs on **http://127.0.0.1:5001** (set by `FLASK_RUN_PORT=5001` in `.env`; the sibling `N8NHIRING v1.0` dev app uses 5002). `python wsgi.py` honours the same variable.

**Production (Gunicorn)** – workers = `2 × CPU + 1` (set in `gunicorn.conf.py`):

```bash
mkdir -p logs
gunicorn -c gunicorn.conf.py wsgi:app
```

A systemd unit example:

```ini
[Service]
User=www-data
WorkingDirectory=/srv/wbe_negotiation
EnvironmentFile=/srv/wbe_negotiation/.env
ExecStart=/srv/wbe_negotiation/.venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
```

**Nginx** – see `deploy/nginx.conf.example`. It serves `/static/` directly (1-year cache) and proxies everything else to Gunicorn.

**Tests**

```bash
python -m unittest discover -s tests -v
```

---

## 4. Features at a glance

* **Login / Logout / Change password** – generic login errors, inactive users blocked, safe `next` redirect, CSRF on every POST (logout included).
* **Dashboard** – total + per-status counts and average profitability from **one grouped aggregate query** (NULLs ignored; never cached) + latest 8 candidates.
* **Candidates list** – case-insensitive *contains* search (name, code, position, client), sortable headers, AND-combined filters (status, department, urgency, scarcity, profitability sign), page size 10/20/50. Search, sort, filters, page size and page number all live in the query string; changing search/filters resets to page 1. Search is debounced (300 ms) and swaps only the results block (no full-page flicker; works without JS too). **Closed negotiations are hidden**: the status filter opens on “All open”, and picking `Closed` is how you look at them.
* **Stage is never set by hand** – there is no status dropdown anywhere. The stage moves through the workflow (see below): `Draft → InProcess → Generated → Closed`.
* **Add / Edit candidate** – 4-step wizard (Candidate → Client → Evaluation → Review & Save) with progress bar. Client-side validation per step, full server-side validation on the final submit only, and on error the page re-opens on the first step with an error, with every value preserved. Nothing is written to the database before the final submit. A new candidate starts at `Draft`; editing never moves the stage.
* **Candidate code** `WBE-YYYY-XXXX` – generated inside the creating transaction with a locking read and retry on unique conflict; resets each IST year; never touched on edit.
* **Profitability** – `((client_budget − expected_ctc) / client_budget) × 100` using `Decimal`, 2 dp, recalculated and stored on every create/edit. Green / red / muted “N/A”.
* **Summary page** – profitability card, Chart.js radar (server-built data, fixed 0–100 scale), key metrics, client and evaluation summaries, rating indicators, flags.
* **Delete** – Admin only: button hidden for HR **and** `403` enforced on the server; POST + CSRF + confirmation modal; child rows removed by `ON DELETE CASCADE`.
* **Excel export** – same `build_candidates_query` and same query string as the list; styled header, frozen header row, autofilter, auto column widths (capped), Indian ₹ number format, labels instead of TINYINT numbers, IST date text, timestamped filename.

### Radar chart scaling

| Axis | Scaling |
|---|---|
| Client Urgency, Skill Scarcity, Availability of Talent, Risk of Losing Candidate | −1 / 0 / 1 → 0 / 50 / 100 |
| Client Flexibility | Yes = 100, No = 0 |
| On Bench | not on bench = 0; on bench = `min(bench_months / 6, 1) × 100` |

### The negotiation workflow

The stage is driven by the workflow, never by a dropdown. The transitions live in
`app/services.py` (`request_script`, `save_negotiation`, `sync_script_statuses`).

| Stage | How it is reached | What it means |
|---|---|---|
| `Draft` | created in the wizard | the data is being captured |
| `InProcess` | **Generate negotiation script** (also the bulk *Request script* button on the list) | the script was requested, n8n is generating it |
| `Generated` | the script links appear in `ng_5_negotiation_results` | the script exists, ready to negotiate |
| `Closed` | **Close negotiation** on the negotiation page | the outcome is recorded in `ng_6_negotiations` |

The two halves of a negotiation live in two tables, on purpose:

* `ng_5_negotiation_results` – the **machine** half: the generated script, the two PDF links, when and by whom it was generated. Written by the n8n workflow.
* `ng_6_negotiations` – the **human** half: the amount offered, the salary the candidate confirmed, the remarks, who closed it and when. Written by the app.

A closed negotiation stays in the database and is out of the open pipeline. It is hidden from the
candidate list, the dashboard table and the Excel export, and it is looked up in the
**Negotiations** register (`/negotiations`, tabs *Open / Closed / All*).

#### What the n8n workflow has to do

The workflow writes the database directly, so it owns the step that moves a candidate to `Generated`:

```sql
-- 1. the workflow picks up the candidates that are waiting for a script
SELECT id, candidate_code FROM ng_2_candidates
 WHERE status = 'InProcess' AND script_requested_at IS NOT NULL;

-- 2. it generates both PDFs, uploads them to Drive and stores the links
INSERT INTO ng_5_negotiation_results
       (candidate_id, full_playbook_pdf_path, quick_reference_pdf_path, generated_at, generated_by)
VALUES (:candidate_id, :playbook_url, :quick_reference_url, NOW(), :user_id);

-- 3. and it moves the candidate on
UPDATE ng_2_candidates SET status = 'Generated' WHERE id = :candidate_id;
```

Two rules the app holds on to:

1. **A candidate is `Generated` only when a link exists.** `sync_script_statuses()` runs on the dashboard, the list and every candidate page: a candidate that is `InProcess` while a link is in `ng_5` is moved to `Generated` by the app. The workflow may forget step 3 and the stage is still right.
2. **A negotiation is only closed through the form.** `ng_6_negotiations` gets its row, and both the amount offered and the confirmed salary are required, so a closed negotiation always says what was agreed.

The workflow may take a while. The negotiation page shows `InProcess` with the time the script was requested, and the candidate becomes `Generated` the moment the links land.

---

## 5. Performance notes

**Database**
* `build_candidates_query` joins ng_2 + ng_3 + ng_4 once and loads them with `contains_eager` (the same join that search/filter/sort need), so no N+1 and no second join. The TEXT columns (`notes`, `key_strengths`, `key_concerns`, `notes_from_client`) are deferred on the list and dashboard; the export loads them.
* The list page runs a constant number of queries (user, count, page, departments) regardless of page size – verified in the tests. Pagination is SQL `LIMIT/OFFSET`.
* Engine options: `pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=280`; MySQL session `time_zone='+05:30'` is set on every connection.
* Search uses `%term%` (case-insensitive). That cannot use a B-tree index by design; fine for thousands of rows.

**Front end**
* Chart.js loads **only** on the summary page. All scripts use `defer`; CDN versions are pinned (Bootstrap 5.3.3, Chart.js 4.4.3). System font stack, inline SVG logo, no image requests.
* Flask-Compress (gzip) is enabled; static files send `Cache-Control: max-age=31536000` (`SEND_FILE_MAX_AGE_DEFAULT`). CSS/JS links carry `?v=1.0` – bump it when you change them.

**The biggest speed factor: database latency.**
Run the app on the **same server / region as MySQL** and connect through `localhost` or a private IP. A remote database over the public internet adds tens to hundreds of milliseconds to *every* query and will dominate page-load time. If you must use a remote MySQL, enable SSL (`DB_SSL_CA`) and keep the app close to it.

---

## 6. Security checklist

* Password hashing with Werkzeug; passwords are never logged or flashed.
* CSRF on all POST routes (delete, script request, negotiation, bulk request, logout, change password, forms); CSRF failures return `400`.
* Cookies: `HttpOnly`, `SameSite=Lax`, `Secure` in Production.
* Inactive users cannot log in and are signed out on their next request.
* Custom 404 / 403 / 400 / 500 pages (session is rolled back on 500). Logs rotate in `logs/app.log`.
* The stage cannot be set by hand: there is no route that writes an arbitrary status, and a negotiation can only be closed through the form (which requires both amounts).

## 7. Notes & limits

* `candidate_code` uses `max + 1` for the current year. If the highest-numbered candidate of a year is deleted, its number can be reused – deleting the newest record is the only way to see this.
* The Excel rupee format uses Excel's two-condition number format to get lakh/crore grouping; it is designed for non-negative amounts (all rupee fields are validated ≥ 0).
* HR users can currently see all candidates (as specified for Phase 1).
* Closed negotiations are hidden from the candidate list, the dashboard table and the export. They are in the **Negotiations** register and in the list when the status filter is set to `Closed`.
* The negotiation register shows the 200 most recent rows; use the search box for older ones.

## UI refresh (teal design system)

The interface follows the Stitch "N8N Hiring Intelligence" reference: teal tokens (#0F766E), top navigation, KPI cards,
segmented controls, stepper cards and a live simulator in the wizard.

New, fully data-backed features:

| Area | What it does |
|---|---|
| Dashboard | 6 KPI cards, tabs (All / Action Required / High Urgency / Script Ready) with live counts, urgent actions, account margin spread, open-pipeline economics. Still ONE grouped aggregate for the KPIs. |
| Candidates | KPI cards that follow the current filters, Sort-by select, row checkboxes + **Request script in bulk** (`POST /candidates/bulk-script`, CSRF, validated), **quick-view drawer** (`GET /candidates/<id>/quick`), Ctrl/⌘+K to focus search. Excel export still reuses the same query as the list. |
| Wizard | Segmented Yes/No/High-Medium-Low controls, candidate chip, **live simulator** (margin vs target, hike %, offer ladder, leverage index). |
| Summary | Hero with margin vs target, gross margin and per-month value, compensation ladder, billing-allocation bar, **negotiation stage card** (script links + the next action), Print/Save PDF, Copy link. |
| Negotiation | `/candidates/<id>/negotiation`: the script PDFs, the amount offered, the confirmed salary, the remarks, and **Close negotiation**. `/negotiations`: the register of open and closed negotiations. |
| Insights | `/insights`: margin by client/department, urgency/scarcity/risk distribution, deficit list and watchlist. |
| Header | Bell fed lazily by `/api/attention`, help dialog explaining the formula, "Keep me signed in" (30 days). |

Configuration: `TARGET_MARGIN` (default `22`) is the profitability % used for "Healthy / Below target / Deficit" labels.
Chart.js is still loaded only on the candidate summary page.
