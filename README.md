# FoodSpend Insights: Personalized Nutrition Analytics

**Question answered:** *"Based on my food history, preferences, current health indicators and budget, what is a suitable meal for me to eat next, and why?"*

The project is a full-stack analytics and decision-support application:

- A **365-day synthetic dataset** of food orders, preference feedback, health measurements and meal options, with a cleaning pipeline and a data-quality report.
- A **MySQL** database loaded by a validated, idempotent import command.
- A **Django REST Framework** API for spending, nutrition, preference and health analytics, a **transparent rule-based next-meal recommender**, a what-if simulator and a budget simulator.
- A **React + Vite + Bootstrap + Plotly** dashboard with nine pages.
- **Jupyter notebooks** and **SQL scripts** that reproduce every figure with the same formulas the API uses.

> ⚠️ **All data is synthetic** and describes one fictional person. The recommendations are decision support from the provided options. They are not medical advice, they do not diagnose or treat anything, and they do not reflect real-time availability or current prices.

## Technology stack
| Layer | Tools (tested versions) |
|---|---|
| Frontend | React 18.3, Vite 5.4, React Router 6.28, Bootstrap 5.3, Plotly.js 2.35 |
| Backend | Python 3.14, Django 6.1, Django REST Framework 3.18, django-cors-headers, mysqlclient 2.3 |
| Database | MySQL 8.0 (SQLite fallback for quick runs) |
| Analytics | pandas 3.1, NumPy 2.5, Matplotlib 3.11, Jupyter (nbconvert/notebook), SQL |
| Docs/deck | Markdown, python-pptx |

## Directory structure
```
├── backend/
│   ├── config/                 Django settings & URLs (reads backend/.env)
│   ├── apps/
│   │   ├── catalog/            vendors, foods, nutrition, meal options
│   │   ├── orders/             orders, order items, item-level history
│   │   ├── preferences/        feedback, preference summary
│   │   ├── health/             person, measurements, goals, reference ranges
│   │   ├── analytics/          dataset loader, analytics views, import_data command
│   │   └── recommendations/    next-meal, simulate, budget, sensitivity endpoints
│   ├── foodspend_core/         shared formulas, analytics and recommender (no Django)
│   ├── tests/                  35 unit + integration tests
│   ├── requirements.txt, .env.example, manage.py
├── frontend/                   React app (src/pages, components, hooks, services, utils, styles)
├── data/raw | data/processed   synthetic CSVs (see data/README.md)
├── analysis/
│   ├── scripts/                generate_synthetic_data.py, clean_data.py, validate_sql.py
│   ├── notebooks/              01 data quality, 02 spending/nutrition/preferences/health, 03 recommendation/scenarios
│   ├── sql/analysis_queries.sql
│   └── reports/                data-quality report, import report, SQL validation, figures/
├── docs/                       architecture, database schema, API documentation, presentation
├── scripts/setup_mysql.ps1     creates the MySQL database + app user and writes backend/.env
├── DECISIONS.md
└── README.md
```

## Setup on Windows (PowerShell, from the project root)

### 1. Prerequisites
- Python 3.12+ (tested on 3.14)
- Node.js 18+ (tested on 24)
- MySQL Server 8.0 running on `localhost:3306`
- Git

### 2. Python environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt -r analysis\requirements.txt
```

### 3. Create the MySQL database and configure `.env`
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_mysql.ps1
```
The script prompts for the MySQL **root** password locally and never stores it. It then:

- creates the `foodspend` database and a `foodspend` user with a random password;
- grants that user access to `foodspend` and `test_foodspend`;
- writes `backend\.env`, which is gitignored.

To configure manually instead, copy `backend\.env.example` to `backend\.env` and fill it in.

*No MySQL available?* Set `DB_ENGINE=sqlite` in `backend\.env` (or `$env:DB_ENGINE="sqlite"`). Every step below then works unchanged.

### 4. Generate, clean and import the data
```powershell
python analysis\scripts\generate_synthetic_data.py    # data/raw (deterministic, seed 20251027)
python analysis\scripts\clean_data.py                 # data/processed + analysis/reports/data_quality_report.md
cd backend
python manage.py migrate
python manage.py import_data                          # validates, upserts, reconciles; safe to re-run
```
`import_data --dry-run` validates without writing. The import prints rejected rows and a reconciliation of CSV totals against database totals.

### 5. Start the backend
```powershell
cd backend
python manage.py runserver 127.0.0.1:8000
```
Check: open http://127.0.0.1:8000/api/analytics/dashboard/ and you should see JSON.

### 6. Start the frontend (second terminal)
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Vite proxies `/api` to Django, so a dashboard showing numbers confirms that frontend, API and database are connected. If the API is down, the page shows "Cannot reach the API" with a Retry button.

### 7. Run the tests
```powershell
cd backend
python manage.py test tests                 # 35 tests; on MySQL the app user needs rights on test_foodspend
cd ..
python analysis\scripts\validate_sql.py     # 48 SQL-vs-pandas checks -> analysis/reports/sql_validation.md
cd frontend; npm run build                  # production build compiles every page
```

### 8. Run the notebooks
```powershell
python analysis\notebooks\build_notebooks.py          # (re)creates the .ipynb files
jupyter nbconvert --to notebook --execute --inplace analysis\notebooks\*.ipynb
# or interactively:  jupyter notebook analysis\notebooks
```
Figures are written to `analysis/reports/figures/`.

### 9. Rebuild the presentation
```powershell
python docs\build_presentation.py     # docs/FoodSpend_Insights.pptx, numbers computed from data/processed
```

## Using the dashboard
| Page | What it does |
|---|---|
| **Dashboard** | KPIs, monthly spending, category spending, frequent foods, nutrition vs targets, preferences, health, suggested meal. The date presets and pickers refilter everything. |
| **Food history** | Item-level records with filters (date, meal, record type, category, consumption status, search) and pagination. Shows purchased and consumed nutrients separately. |
| **Nutrition** | Weekly or monthly trends of logged intake against documented targets, status labels and completeness notes. |
| **Preferences** | Ratings per food, purchases vs ratings, the full preference table and a feedback form. Saving a dislike removes that food from recommendations immediately. |
| **Health indicators** | Indicator trend with a shaded reference range, a summary table and a validated measurement form. |
| **Next meal** | Meal type, goal, adjustable target, budget, source and ranking weights. Shows the recommended meal, reasons, confidence, four alternatives with trade-offs, comparison charts, the ranking table and the method. |
| **What-if simulator** | Change servings, add, substitute or remove items. The server recomputes nutrients and cost and compares the result with the baseline. |
| **Budget simulator** | Budget slider or input. Shows feasible options, remaining budget and utilisation, cost vs goal nutrient, and sensitivity to budget and weights. |
| **Data & evidence** | Key findings, cleaning and import checks, the join-duplication check, disclosures, assumptions and limitations. |

## Key results (synthetic data, 2025-10-27 to 2026-10-26)
- **Spending:** ₹1,48,988 across 648 transactions. Delivery accounts for 71%; tax, delivery and platform charges add 14.1%.
- **Logged intake:** protein averages 50.9 g/day against a 65.5 g target (Below target); fibre 17.4 g against 30 g (Below target).
- **Purchases ≠ liking:** Veg Hakka Noodles is the 9th most purchased food but is rated 2.8/5 with the latest label "disliked". Spearman correlation between rating and purchases is 0.44.
- **Default recommendation** (lunch, protein, ₹350): Home Paneer Bhurji with 2 Roti, ₹85, 26 g protein, 520 kcal, confidence High. The best delivery-only option is Idli Sambar with boiled eggs from the pantry, ₹139.
- **Weight:** fell 3.3 kg over the year. This is reported as an association only.

## Known limitations
- All data is synthetic, and nutrient values are unverified estimates. Fibre is unknown for two dishes and is reported as unknown, not zero.
- Intake only covers logged meals, so it is likely an underestimate. Grocery purchases are not assumed to be eaten.
- Prices are historical. Availability is limited to the dataset's options. Home-meal costs are ingredient estimates.
- Meal shares, ranking weights and the ±15% serving uncertainty are documented assumptions.
- The API has no authentication because it is a local single-user tool.
- The Plotly bundle is about 4.9 MB; code-splitting would reduce the first load.
