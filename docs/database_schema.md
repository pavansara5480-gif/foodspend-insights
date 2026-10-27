# Database schema (MySQL 8)

The schema is created by Django migrations (`python manage.py migrate`). Table names are set explicitly with `db_table`. Money columns are `DECIMAL(10,2)` in INR, and nutrient columns are `DECIMAL(8,2)`, nullable to mean "unknown".

```
users 1─* orders 1─* order_items *─1 foods 1─1 food_nutrition
  │          *                          │ 1
  │          └─1 vendors 1─* foods ─────┤
  ├─* food_feedback *─1 foods            └─* meal_options
  │        └─0..1 orders
  ├─* health_measurements
  └─* nutrition_goals                reference_ranges (lookup by indicator)
```

## Tables

### users (`apps.health.Person`)
| Column | Type | Notes |
|---|---|---|
| person_id | VARCHAR(10) **PK** | e.g. U001 |
| display_name | VARCHAR(120) | |
| sex, activity_level | VARCHAR | optional |
| birth_year | SMALLINT NULL | |
| height_cm | DECIMAL(5,1) | CHECK 50 < height < 260 |
| is_synthetic | BOOL | always true here |
| created_at | DATETIME | |

### vendors
| Column | Type | Notes |
|---|---|---|
| vendor_id | VARCHAR(10) **PK** | |
| vendor_name | VARCHAR(120) UNIQUE | |
| channel | VARCHAR(10) | delivery / cafe / grocery / home |
| tax_rate | DECIMAL(5,4) | CHECK 0 ≤ rate < 1 |
| typical_delivery_fee_inr | DECIMAL(8,2) | |

### foods
| Column | Type | Notes |
|---|---|---|
| food_id | VARCHAR(10) **PK** | |
| food_name | VARCHAR(120) UNIQUE | prevents duplicate foods |
| category | VARCHAR(60) INDEX | |
| role | VARCHAR(10) | main / side / pantry / snack / beverage |
| vendor_id | **FK → vendors** (PROTECT) | |
| default_serving_size | DECIMAL(8,2) | CHECK > 0 |
| serving_unit | VARCHAR(4) | g / ml |
| description, is_active | | |

### food_nutrition
| Column | Type | Notes |
|---|---|---|
| nutrition_id | VARCHAR(10) **PK** | |
| food_id | **FK → foods**, UNIQUE (1:1) | CASCADE |
| basis | VARCHAR(12) | per_serving / per_100g / per_100ml |
| basis_quantity, basis_unit | DECIMAL, VARCHAR | values apply to this amount; CHECK quantity > 0 |
| calories_kcal, protein_g, carbs_g, fat_g, fiber_g | DECIMAL(8,2) NULL | NULL = unknown; CHECK ≥ 0 |
| nutrition_source, source_date | | provenance |

### meal_options
| Column | Type | Notes |
|---|---|---|
| meal_option_id | VARCHAR(10) **PK** | |
| food_id | **FK → foods** | UNIQUE(food_id, meal_type) |
| meal_type | VARCHAR(10) | breakfast / lunch / snack / dinner |
| serving_size, serving_unit | | CHECK size > 0 |
| price_per_serving_inr | DECIMAL(8,2) | CHECK > 0 |
| allowed_servings | VARCHAR(40) | e.g. `1,1.5` |
| availability_status, price_source, price_date | | historical price, not live |

### orders
| Column | Type | Notes |
|---|---|---|
| order_id | VARCHAR(12) **PK** | |
| person_id | **FK → users** | |
| order_datetime / order_date | DATETIME / DATE INDEX | |
| meal_type | VARCHAR(15) | + `not_applicable` for grocery |
| meal_type_inferred | BOOL | set when inferred from the time of day |
| record_type | VARCHAR(20) INDEX | delivery_order / cafe_purchase / grocery_purchase / home_meal |
| vendor_id | **FK → vendors** | |
| items_subtotal_inr, order_discount_inr, tax_inr, delivery_fee_inr, other_charges_inr | DECIMAL(10,2) | CHECK all ≥ 0 |
| final_total_inr | DECIMAL(10,2) | **CHECK final = subtotal − discount + tax + delivery + other** |
| total_recomputed | BOOL | raw total disagreed and was recomputed |
| counts_as_spending | BOOL | false for home meals (estimated ingredient cost) |

### order_items
| Column | Type | Notes |
|---|---|---|
| order_item_id | VARCHAR(12) **PK** | |
| order_id | **FK → orders** (CASCADE) | |
| food_id | **FK → foods** (PROTECT) | |
| food_name_raw | VARCHAR(160) | the name exactly as exported |
| quantity | DECIMAL(8,2) | CHECK > 0 |
| serving_size, serving_unit | | size per unit; CHECK > 0 |
| unit_price_inr, item_discount_inr, line_total_inr | DECIMAL | CHECK price, discount ≥ 0 |
| consumption_status | VARCHAR(20) | consumed / partially_consumed / not_consumed / unknown |
| portion_consumed | DECIMAL(4,2) NULL | CHECK 0–1; NULL when unknown |
| food_match_method | VARCHAR(20) | food_id / normalised_name / api |

### food_feedback
| Column | Type | Notes |
|---|---|---|
| feedback_id | VARCHAR(12) **PK** | |
| person_id | **FK → users** | |
| food_id | **FK → foods** | |
| order_id | **FK → orders** NULL (SET NULL) | survey feedback has no order |
| feedback_date | DATE INDEX | |
| rating | SMALLINT | **CHECK 1–5** |
| preference_label | VARCHAR(12) | liked / acceptable / disliked / avoid |
| comment, would_buy_again, serving_preference | | |
| order_link_removed, created_via | | data lineage |

### health_measurements
| Column | Type | Notes |
|---|---|---|
| measurement_id | VARCHAR(12) **PK** | |
| person_id | **FK → users** | UNIQUE(person, date, indicator) |
| measurement_date | DATE INDEX | |
| indicator | VARCHAR(30) | weight / waist_circumference / systolic_bp / diastolic_bp / fasting_glucose |
| value | DECIMAL(7,2) | CHECK > 0; plausibility ranges enforced at import and in the API |
| unit, source, notes | | |

### nutrition_goals
`goal_id` **PK**, `person_id` **FK**, `goal_key` (UNIQUE per person), `nutrient`, `direction` (at_least/at_most), `target_value` (CHECK > 0), `unit`, `reference_source`, `reference_date`, `is_active`.

### reference_ranges
`indicator` **PK**, `lower` NULL, `upper` NULL, `unit`, `source`.

## Join rules that prevent double counting
- Spending is summed on `orders.final_total_inr`, never after joining to `order_items`.
- Category/food spending is summed on `order_items.line_total_inr`, and order-level charges are reported as a separate row.
- `orders → vendors` and `order_items → foods → food_nutrition` are many-to-one or one-to-one joins, so they cannot fan out. pandas merges assert this with `validate="m:1"`.
