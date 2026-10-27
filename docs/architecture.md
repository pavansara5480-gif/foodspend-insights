# Architecture

```
 data/raw/*.csv ──clean_data.py──► data/processed/*.csv ──manage.py import_data──► MySQL
 (synthetic generator)            (+ rejected_records.csv,                          │
                                   data_quality_report)                             │ Django ORM
                                                                                    ▼
        analysis notebooks ◄── foodspend_core (pure Python formulas) ──► apps/analytics/services.py
        SQL validation                                                              │ get_dataset()
                                                                                    ▼
 React (Vite) ──fetch /api/*──► Vite dev proxy ──► Django REST Framework views ── JSON
   Plotly charts, simulators                                 (recommendations, scenarios, analytics)
```

## Layers

| Layer | Location | Responsibility |
|---|---|---|
| Data generation | `analysis/scripts/generate_synthetic_data.py`, `catalog.py` | Seeded and reproducible. Produces linked raw tables with deliberate quality issues. |
| Cleaning | `analysis/scripts/clean_data.py` | Validates and standardises data, rejects invalid rows with reasons, and writes the quality report. |
| Database | `backend/apps/*/models.py` | Normalised MySQL schema with primary/foreign keys, unique and check constraints (see `database_schema.md`). |
| Import | `apps/analytics/management/commands/import_data.py` | Validates every row again, upserts by primary key in one transaction (idempotent), and reconciles totals with the CSVs. |
| Calculation core | `backend/foodspend_core/` | Framework-free formulas (`formulas.py`), DataFrame analytics (`analytics.py`) and the recommender/scenario engine (`recommender.py`). The API and notebooks both use it. |
| API | `backend/apps/*/views.py` | Thin views: parse and validate input, call the core, return JSON. Errors use a consistent `{"error": {...}}` shape. |
| Frontend | `frontend/src` | React Router pages, a `useApi` hook, a Plotly wrapper and shared UI parts. There are no hard-coded metrics; every value comes from the API. |

## Data flow for a request

1. React calls, for example, `GET /api/recommendations/next-meal/?goal=protein&budget=350`.
2. The view validates query parameters (`apps/analytics/params.py`); invalid input returns 400.
3. `services.get_dataset()` returns a cached `Dataset` of pandas DataFrames built from the ORM. Model `post_save`/`post_delete` signals and the import command invalidate the cache, so new feedback or measurements apply on the next request.
4. `foodspend_core.recommender.recommend()` generates candidates, applies constraints, scores and ranks them, then builds alternatives, reasons and a confidence indicator.
5. The view converts NaN/NumPy/date values to JSON and returns them; React renders tables and charts.

## Analytics pipeline

Spending is aggregated at order level. Nutrition uses `item_nutrition()`, where the amount is quantity × serving ÷ basis quantity × value, and consumed amounts are multiplied by the portion eaten. Preferences come from explicit feedback, with purchase counts reported separately. Health summaries add a BMI derived from height. `key_findings()` states only observed associations.

## Recommendation pipeline

1. **Context:** goal and target (documented or user-overridden), meal share, calorie allowance, and the last 30 days of logged intake.
2. **Candidates:** each main dish listed for the meal type, at each allowed serving, alone or with one add-on (a side from the same vendor, or a previously purchased pantry food).
3. **Constraints:** within budget, and the latest label isn't disliked/avoid.
4. **Score:** weighted goal, preference (shrunk mean rating) and cost.
5. **Output:** the recommendation, alternatives (substitution, larger serving, addition, lowest cost), the top-10 ranking, exclusions, the method and a disclaimer.

Scenarios re-evaluate a baseline meal and a modified meal (after `set_servings`/`add`/`remove`/`substitute` operations) with the same `evaluate()` function. The client never supplies prices or nutrients.

## Configuration and security

- Settings are read from `backend/.env` (template: `.env.example`). The database is MySQL by default; `DB_ENGINE=sqlite` is a no-server fallback.
- CORS is limited to the Vite origin, and the Vite dev proxy means the browser normally talks to a single origin.
- The API has no authentication because it is a local single-user analysis tool. Add Django session authentication before exposing it, because it holds (synthetic) health data.
