# DECISIONS

**Data sources.** No suitable public personal history exists, so all data is **synthetic**: one fictional person, 365 days (2025-10-27 to 2026-10-26), produced by a seeded script (`analysis/scripts/generate_synthetic_data.py`, seed 20251027). Nutrient values approximate typical published values (IFCT 2017, USDA FoodData Central) but were not verified item by item. Targets cite ICMR-NIN 2020 (protein 0.83 g/kg; 2,110 kcal sedentary man), DGA 2020-25 (fibre 14 g/1,000 kcal), WHO (fat ≤30% energy) and IOM (carbohydrate 45–65%).

**Cleaning and matching.** Exact duplicates are removed. Units are standardised. A blank food ID is resolved only by an exact normalised-name match. Invalid quantities, ratings, orphans and implausible measurements are rejected and logged, never guessed. Unknown nutrients stay NULL.

**Formulas.** Nutrient = quantity × serving ÷ basis quantity × value. Order total = subtotal − discount + tax + delivery + other. Spending is summed at order level (no join duplication) and excludes home-meal ingredient estimates. Intake counts only logged consumption (× portion eaten). Purchases are never assumed eaten or liked.

**Recommendation.** This is rule-based. Hard constraints exclude options over budget, foods not listed for the meal type, and foods whose latest label is disliked or avoid. The score is 0.5 × goal + 0.3 × preference + 0.2 × cost:

- **Goal:** progress toward the meal's share of the daily target, capped at 100%, blended with calorie fit.
- **Preference:** the food's mean rating, shrunk toward the person's overall mean.
- **Cost:** 1 − cost ÷ budget.

Ties go to higher preference, then lower cost.

**Assumptions.** Meal shares are 25/35/10/30%. Serving uncertainty is ±15%. Fees are the vendor's median from the last 90 days.

**Limitations.** Logging is incomplete. Prices are historical. Availability is not real-time. Health trends are associations, not causation. This is not medical advice.
