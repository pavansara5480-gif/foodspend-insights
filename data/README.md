# Data

> **Everything in this folder is SYNTHETIC.** It describes one fictional person ("Synthetic Persona A") and is
> not real customer or patient data.

| Folder | Contents |
|---|---|
| `raw/` | Output of `analysis/scripts/generate_synthetic_data.py`. It deliberately contains data-quality problems (listed in `raw/MANIFEST.json`) so the cleaning step can show how it detects and handles them. |
| `processed/` | Output of `analysis/scripts/clean_data.py`: the validated tables loaded into MySQL, plus `rejected_records.csv`, which gives every rejected row and the rule that rejected it. |

Regenerate everything (it's deterministic):

```powershell
.venv\Scripts\python analysis\scripts\generate_synthetic_data.py
.venv\Scripts\python analysis\scripts\clean_data.py
```

## Tables (linked by stable IDs)

| File | Key | Links | Notes |
|---|---|---|---|
| `users.csv` | `user_id` | — | Height is used to derive BMI. |
| `vendors.csv` | `vendor_id` | — | Channel (delivery/cafe/grocery/home), tax rate, typical delivery fee. |
| `foods.csv` | `food_id` | `vendor_id` | Role: main / side / pantry / snack / beverage. |
| `food_nutrition.csv` | `nutrition_id` | `food_id` (1:1) | `basis` is `per_serving` or `per_100g`, with `basis_quantity` and `basis_unit`. Blank = unknown. |
| `meal_options.csv` | `meal_option_id` | `food_id` | Candidate foods per meal type, with latest price per serving and allowed serving multipliers. |
| `orders.csv` | `order_id` | `user_id`, `vendor_id` | Order-level money: subtotal, discount, tax, delivery fee, other charges, final total. `record_type` is delivery_order, cafe_purchase, grocery_purchase or home_meal. |
| `order_items.csv` | `order_item_id` | `order_id`, `food_id` | Quantity × serving size (g/ml), unit price, line total, `consumption_status`, `portion_consumed`. |
| `food_feedback.csv` | `feedback_id` | `food_id`, optional `order_id` | Rating 1–5, label (liked/acceptable/disliked/avoid), comment, willingness to buy again, serving preference. |
| `health_measurements.csv` | `measurement_id` | `user_id` | Weight (weekly), waist and blood pressure (monthly), fasting glucose (quarterly). There's a gap in March 2026. |
| `nutrition_goals.csv` | `goal_id` | `user_id` | Protein, fibre and calorie targets, each with a cited reference. |
| `reference_ranges.csv` | `indicator` | — | Documented ranges for status labels (BMI, glucose, BP, waist, fat % and carbohydrate % of energy). |

## Generation method

The generator simulates each day:

- **Breakfast:** home oats or upma, a delivery tiffin, or pantry banana and eggs.
- **Lunch:** delivery on most weekdays, otherwise a home thali.
- **Snack:** cafe tea or snack, or pantry fruit and nuts.
- **Dinner:** a mix of home and delivery.
- **Groceries:** a run every 4–6 days.

A 3-week travel period produces a logging gap. Choice frequencies are driven by convenience weights that differ from the person's hidden "true" ratings, so purchase frequency and liking deliberately diverge.

Other rules:

- Prices drift about 6% a year.
- 25% of delivery orders get a discount.
- Platform fees start in January 2026.
- Feedback is sampled from the hidden ratings with noise.
- Two foods have unknown fibre.
