# API documentation

Base URL: `http://127.0.0.1:8000/api/`. When the app runs through Vite, it is `http://localhost:5173/api/` (proxied). All responses are JSON.

**Errors** use one shape:

```json
{"error": {"code": "invalid", "message": "Invalid request", "details": {"budget": "must be >= 0"}}}
```

| Status | When |
|---|---|
| 400 | Invalid parameters or an invalid body. Scenario rule violations use `code: "invalid_input"`. |
| 404 | Unknown ID. |
| 503 | The database is empty (`code: "no_data"`). Run `import_data`. |

Dates use `YYYY-MM-DD`. Wherever `start`/`end` are accepted, `start` must be on or before `end`.

## Catalogue
| Method | Endpoint | Parameters | Returns |
|---|---|---|---|
| GET | `/foods/` | `category`, `role`, `search` | Foods with vendor and nutrition |
| GET | `/foods/{food_id}/` | | Food + nutrition + meal options + preference row |
| GET | `/nutrition/` | | Nutrition reference (basis, values, source) |
| GET | `/meal-options/` | `meal_type` | Candidate options with price per serving |
| GET | `/vendors/` | | Vendors, channel, tax rate |

## Orders and history
| Method | Endpoint | Parameters | Notes |
|---|---|---|---|
| GET | `/orders/` | `start`, `end`, `meal_type`, `record_type`, `category`, `food`, `page` | Paginated (25), order-level money + items |
| GET | `/orders/{order_id}/` | | One order with its items |
| POST | `/orders/` | body below | Prices, tax and totals are computed by the server |
| GET | `/history/` | `start`, `end`, `meal_type`, `record_type`, `category`, `consumption`, `search`, `page`, `page_size` (≤200) | One row per item, with purchased and consumed nutrient estimates |

`POST /orders/` example:

```json
{"order_datetime": "2026-10-26T13:00", "meal_type": "lunch", "record_type": "delivery_order",
 "vendor_id": "V02", "delivery_fee_inr": 35,
 "items": [{"food_id": "F005", "quantity": 1, "consumption_status": "consumed"}]}
```

Validation rules:

- Foods must belong to the order's vendor. Home meals may use home or pantry foods.
- The meal type must be `not_applicable` exactly when the order is a grocery purchase.
- The discount cannot exceed the subtotal.
- `portion_consumed` must be empty when consumption is `unknown`.

## Preferences
| Method | Endpoint | Notes |
|---|---|---|
| GET | `/feedback/?food=&label=` | Paginated feedback |
| POST | `/feedback/` | `{"food": "F013", "rating": 2, "preference_label": "disliked", "comment": "..."}`. Rating must be 1–5; "liked" with 1–2 or "disliked" with 4–5 is rejected; future dates are rejected; a linked order must contain the food. |
| PATCH | `/feedback/{id}/` | Update label, rating or comment (same validation) |
| GET | `/preferences/summary/` | Summary, rating distribution, Spearman rating-vs-purchases, per-food table |
| GET | `/preferences/excluded/` | Foods whose latest label is disliked/avoid |

## Health
| Method | Endpoint | Notes |
|---|---|---|
| GET | `/health/measurements/?indicator=&start=&end=` | Raw measurements |
| POST | `/health/measurements/` | `{"measurement_date": "2026-10-26", "indicator": "weight", "value": 78.6}`. The unit is set by the server; plausibility ranges apply (weight 30–250 kg, …); one reading per indicator per day. |
| GET | `/health/summary/?start=&end=` | Per-indicator first/latest/change, reference range, latest status, and series (with derived BMI) |
| GET | `/goals/` | Documented nutrition targets with sources |
| GET | `/reference-ranges/` | Ranges used for status labels |

## Analytics
| Method | Endpoint | Parameters | Returns |
|---|---|---|---|
| GET | `/analytics/dashboard/` | `start`, `end` | Spending summary, monthly spending, categories, top foods, nutrition vs goals, preferences, health, recommendation preview |
| GET | `/analytics/spending/` | `start`, `end` | Summary and components; spending by month, category, meal type, vendor and record type; meal-source pattern |
| GET | `/analytics/frequency/` | `start`, `end`, `top` | Purchase events per food |
| GET | `/analytics/nutrition/` | `start`, `end`, `freq` = `W`/`M` | Summary vs targets, energy distribution, completeness, trend, daily values |
| GET | `/analytics/findings/` | | Computed key findings |
| GET | `/analytics/data-quality/` | | Cleaning report, import report, live DB checks (including join duplication), disclosures |

## Recommendations and scenarios
### `GET /recommendations/next-meal/`
| Parameter | Default | Rule |
|---|---|---|
| `meal_type` | lunch | breakfast / lunch / snack / dinner |
| `goal` | protein | protein / fiber / calories |
| `budget` | 350 | 0–100000 (₹) |
| `target` | documented | override for the daily goal target |
| `source` | any | any / delivery / home |
| `w_goal`, `w_pref`, `w_cost` | 0.5 / 0.3 / 0.2 | 0–1; re-normalised; not all zero |

Response fields:

| Field | Contents |
|---|---|
| `context` | Goal, targets, meal share, recent 30-day intake |
| `recommended` | Items, nutrients (±15% range), cost breakdown, budget metrics, goal contribution, scores, reasons, confidence |
| `alternatives[]` | substitution / serving_increase / addition / budget_saver, each with a `tradeoff` against the recommendation |
| `ranking[]` | Top-10 candidates |
| `excluded_by_feedback[]` | Foods excluded because their latest label is disliked or avoid |
| `method` | The ranking formulas and rules |
| `disclaimer` | The "not medical advice" statement |

If nothing fits, `recommended` is `null` and `message` explains why.

Example response (abridged):

```json
{"recommended": {"name": "Home Paneer Bhurji with 2 Roti", "cost": {"total": 85.0, "tax": 0, "fees": 0},
  "nutrients": {"calories_kcal": 520.0, "protein_g": 26.0, "carbs_g": 40.0, "fat_g": 28.0, "fiber_g": 5.0},
  "budget": {"budget": 350.0, "remaining": 265.0, "utilization_pct": 24.3, "within_budget": true},
  "scores": {"goal": 1.0, "preference": 0.785, "cost": 0.7571, "total": 0.8869},
  "confidence": {"level": "High", "score": 0.9, "factors": ["Nutrient values are synthetic estimates ..."]}}}
```

### `POST /scenarios/simulate/`

```json
{"meal_type": "lunch", "goal": "protein", "budget": 350,
 "baseline": [{"food_id": "F004", "servings": 1}],
 "operations": [{"op": "substitute", "food_id": "F004", "with_food_id": "F008"},
                {"op": "add", "food_id": "F023", "servings": 1}]}
```

`op` is one of `set_servings` (needs `servings`), `add`, `remove` or `substitute` (needs `with_food_id`). Servings must be between 0.25 and 5. Alternatively, send `modified` (a full list of lines) instead of `operations`.

Errors:

- An unknown food, a duplicate item or an empty resulting meal returns 400.
- Removing the last item returns 400 with the message "the modified meal has no items left".

The response contains `baseline` and `modified` (each fully evaluated), `differences` (nutrients, cost, goal progress), `verdict`, `warnings` (for example, a disliked food was added) and `assumptions`.

### `GET /scenarios/budget/?budget=250&meal_type=lunch&goal=protein&source=any`
Returns the best feasible option per main dish (cost, remaining, utilisation, nutrients, goal contribution, preference) and the nearest over-budget options. With no feasible option, it returns `cheapest_candidate_cost`.

### `GET /scenarios/sensitivity/`
Returns the recommended meal under four weight presets and under budgets of ₹100, 150, 250, 350 and 500.
