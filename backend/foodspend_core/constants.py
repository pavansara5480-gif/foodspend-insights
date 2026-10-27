NUTRIENTS = ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]
NUTRIENT_LABELS = {
    "calories_kcal": ("Calories", "kcal"),
    "protein_g": ("Protein", "g"),
    "carbs_g": ("Carbohydrates", "g"),
    "fat_g": ("Fat", "g"),
    "fiber_g": ("Fibre", "g"),
}

# Share of the daily target allotted to each meal (documented assumption, not a clinical rule).
MEAL_SHARES = {"breakfast": 0.25, "lunch": 0.35, "snack": 0.10, "dinner": 0.30}

# Default ranking weights; the API accepts overrides, which are re-normalised to sum to 1.
DEFAULT_WEIGHTS = {"goal": 0.5, "preference": 0.3, "cost": 0.2}

# Labels that exclude a food from recommendations when they are the latest explicit feedback.
EXCLUDED_LABELS = {"disliked", "avoid"}

# Daily energy reference used for the calorie-fit component (ICMR-NIN 2020, sedentary adult man).
DEFAULT_DAILY_KCAL = 2110.0

# Relative uncertainty applied to serving sizes in the sensitivity range.
SERVING_UNCERTAINTY = 0.15

# Record types that represent money actually spent. Home meals carry an *estimated* ingredient cost
# and are excluded from spending totals to avoid double counting unrecorded grocery purchases.
SPENDING_RECORD_TYPES = {"delivery_order", "cafe_purchase", "grocery_purchase"}

STATUS_BELOW, STATUS_WITHIN, STATUS_ABOVE, STATUS_INSUFFICIENT = (
    "Below target", "Within range", "Above target", "Insufficient data")
