"""Generate the SYNTHETIC FoodSpend Insights datasets into data/raw/.

Everything produced here is simulated for one fictional person ("Synthetic Persona A").
It is not real customer or patient data. The script is deterministic (fixed seed), so
re-running it reproduces identical files.

The raw output intentionally contains a small number of data-quality problems
(duplicates, inconsistent names/units, invalid values, broken references) so that
the cleaning step (clean_data.py) can demonstrate detection and documented handling.

Usage:  python analysis/scripts/generate_synthetic_data.py
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np

from catalog import (ALLOWED_SERVINGS, FEEDBACK_COMMENTS, FOODS, GROCERY_PACKS, MEAL_TYPES,
                     RAW_NAME_VARIANTS, VENDORS)

SEED = 20251027
START = date(2025, 10, 27)
END = date(2026, 10, 26)          # inclusive -> 365 days
USER_ID = "U001"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

rng = np.random.default_rng(SEED)
FOOD = {f[0]: dict(zip(["food_id", "name", "category", "role", "vendor_id", "serving_size", "unit",
                         "base_price", "basis", "basis_qty", "kcal", "protein", "carbs", "fat",
                         "fiber", "true_rating"], f)) for f in FOODS}
VENDOR = {v[0]: dict(zip(["vendor_id", "vendor_name", "channel", "tax_rate", "delivery_fee"], v))
          for v in VENDORS}


def price_on(food_id: str, day: date) -> float:
    """List price per unit (per serving, or per 100 g/ml for pantry foods) with ~6%/yr drift."""
    f = FOOD[food_id]
    factor = 1 + 0.06 * (day - START).days / 365
    p = f["base_price"] * factor
    if f["basis"] == "per_serving":
        return float(max(5, round(p / 5) * 5))
    return round(p, 2)


def at(day: date, h0: float, h1: float) -> datetime:
    hours = rng.uniform(h0, h1)
    return datetime.combine(day, time(0)) + timedelta(minutes=int(hours * 60))


def choose(weights: dict[str, float]) -> str:
    keys = list(weights)
    w = np.array([weights[k] for k in keys], dtype=float)
    return keys[rng.choice(len(keys), p=w / w.sum())]


# --------------------------------------------------------------------------- state
orders: list[dict] = []
items: list[dict] = []
feedback: list[dict] = []
counters = {"order": 0, "item": 0, "fb": 0}


def new_id(kind: str, prefix: str, width: int) -> str:
    counters[kind] += 1
    return f"{prefix}{counters[kind]:0{width}d}"


def consumption_for(record_type: str, qty: int) -> tuple[str, str]:
    if record_type == "home_meal":
        return "consumed", "1.0"
    if record_type == "grocery_purchase":
        return "unknown", ""
    if qty >= 2:
        return "partially_consumed", "0.5"   # extra portion shared or saved; logged as half eaten
    r = rng.random()
    if r < 0.85:
        return "consumed", "1.0"
    if r < 0.95:
        return "partially_consumed", "0.5"
    if r < 0.98:
        return "not_consumed", "0.0"
    return "unknown", ""


def add_order(day: date, dt: datetime, meal_type: str, record_type: str, vendor_id: str,
              lines: list[tuple[str, int, float]]) -> str:
    """lines: (food_id, quantity, serving_size). Prices/charges are derived here."""
    order_id = new_id("order", "O", 5)
    subtotal = 0.0
    for food_id, qty, size in lines:
        f = FOOD[food_id]
        if f["basis"] == "per_serving":
            unit_price = price_on(food_id, day) * size / f["serving_size"]
        else:  # priced per 100 g/ml
            unit_price = price_on(food_id, day) * size / 100
        unit_price = round(unit_price, 2)
        item_discount = 0.0
        if record_type == "grocery_purchase" and rng.random() < 0.1:
            item_discount = round(unit_price * qty * 0.1, 2)
        line_total = round(qty * unit_price - item_discount, 2)
        subtotal += line_total
        status, portion = consumption_for(record_type, qty)
        items.append({
            "order_item_id": new_id("item", "I", 6), "order_id": order_id, "food_id": food_id,
            "food_name_raw": f["name"], "quantity": qty, "serving_size": size, "serving_unit": f["unit"],
            "unit_price_inr": unit_price, "item_discount_inr": item_discount, "line_total_inr": line_total,
            "consumption_status": status, "portion_consumed": portion,
        })
        if record_type != "grocery_purchase":
            maybe_feedback(order_id, food_id, day, record_type)
    subtotal = round(subtotal, 2)
    v = VENDOR[vendor_id]
    discount = tax = fee = other = 0.0
    if record_type == "delivery_order":
        if rng.random() < 0.25:
            discount = float(round(min(subtotal * rng.uniform(0.10, 0.20), 100)))
        fee = 0.0 if rng.random() < 0.08 else float(v["delivery_fee"] + rng.choice([-10, 0, 0, 10]))
        other = (5.0 if day >= date(2026, 1, 1) else 0.0) + (10.0 if rng.random() < 0.3 else 0.0)
    if record_type in ("delivery_order", "cafe_purchase"):
        tax = round((subtotal - discount) * v["tax_rate"], 2)
    final = round(subtotal - discount + tax + fee + other, 2)
    orders.append({
        "order_id": order_id, "user_id": USER_ID, "order_datetime": dt.isoformat(timespec="minutes"),
        "meal_type": meal_type, "record_type": record_type, "vendor_id": vendor_id,
        "items_subtotal_inr": subtotal, "order_discount_inr": discount, "tax_inr": tax,
        "delivery_fee_inr": fee, "other_charges_inr": other, "final_total_inr": final,
    })
    return order_id


def maybe_feedback(order_id: str, food_id: str, day: date, record_type: str) -> None:
    f = FOOD[food_id]
    p = {"main": 0.35, "snack": 0.15, "beverage": 0.12, "side": 0.12, "pantry": 0.03}[f["role"]]
    if record_type == "home_meal" and f["role"] == "main":
        p = 0.08
    if food_id in ("F019", "F011", "F018"):
        p = 1.0   # strong explicit opinions recorded for these
    if rng.random() >= p:
        return
    rating = int(np.clip(round(f["true_rating"] + rng.normal(0, 0.6)), 1, 5))
    if food_id == "F019":
        label, comment = "avoid", "Prefers not to eat fish"
        rating = min(rating, 2)
    else:
        label = "liked" if rating >= 4 else "acceptable" if rating == 3 else "disliked"
        comment = str(rng.choice(FEEDBACK_COMMENTS[rating]))
    again = "yes" if rating >= 4 else "maybe" if rating == 3 else "no"
    serving_pref = "same"
    if food_id in ("F008", "F018", "F010") and rng.random() < 0.5:
        serving_pref = "increase"
    elif food_id in ("F011", "F016", "F013") and rng.random() < 0.5:
        serving_pref = "decrease"
    fb_day = day + timedelta(days=int(rng.random() < 0.3))
    feedback.append({
        "feedback_id": new_id("fb", "FB", 4), "user_id": USER_ID, "food_id": food_id,
        "order_id": order_id, "feedback_date": min(fb_day, END).isoformat(), "rating": rating,
        "preference_label": label, "comment": comment, "would_buy_again": again,
        "serving_preference": serving_pref,
    })


# --------------------------------------------------------------------------- history
LUNCH_DELIVERY = {"F013": 12, "F006": 10, "F004": 8, "F005": 8, "F014": 7, "F012": 6, "F008": 5,
                  "F007": 5, "F009": 4, "F010": 4, "F015": 4, "F016": 4, "F011": 3, "F017": 3,
                  "F018": 1, "F019": 2, "F001": 3, "F002": 2}
DINNER_DELIVERY = {"F006": 9, "F004": 8, "F014": 7, "F013": 7, "F015": 6, "F016": 5, "F012": 5,
                   "F005": 5, "F007": 4, "F010": 3, "F008": 3, "F009": 3, "F001": 3, "F017": 3,
                   "F019": 1, "F011": 2}
BREAKFAST_DELIVERY = {"F020": 4, "F002": 4, "F001": 3, "F003": 2}
SIDES = {"V02": "F039", "V04": "F040"}

last_grocery = START - timedelta(days=10)
day = START
while day <= END:
    weekend = day.weekday() >= 5
    travel = date(2026, 3, 9) <= day <= date(2026, 3, 29)   # logging gap (travel)
    restricted = {}
    if day > date(2025, 11, 20):
        restricted["F019"] = 0       # stopped after recording "avoid"
    if day > date(2026, 1, 31):
        restricted["F011"] = 0       # stopped after repeated low ratings

    def weights(base):
        return {k: restricted.get(k, v) for k, v in base.items() if restricted.get(k, v) > 0}

    if travel and rng.random() < 0.85:
        day += timedelta(days=1)
        continue

    # Grocery run every ~5 days
    if (day - last_grocery).days >= int(rng.integers(4, 7)):
        packs = ["F021", "F022", "F023"] + [f for f in ("F024", "F025", "F026") if rng.random() < 0.45]
        add_order(day, at(day, 10, 19), "", "grocery_purchase", "V07",
                  [(f, GROCERY_PACKS[f][0], GROCERY_PACKS[f][1]) for f in packs])
        last_grocery = day

    # Breakfast
    if rng.random() < 0.85:
        r = rng.random()
        dt = at(day, 7.5, 9.5)
        if r < (0.45 if weekend else 0.25):
            fid = choose(BREAKFAST_DELIVERY)
            add_order(day, dt, "breakfast", "delivery_order", "V01", [(fid, 1, FOOD[fid]["serving_size"])])
        elif r < 0.70:
            fid = "F028" if rng.random() < 0.6 else "F029"
            add_order(day, dt, "breakfast", "home_meal", "V08", [(fid, 1, FOOD[fid]["serving_size"])])
        else:
            add_order(day, dt, "breakfast", "home_meal", "V08", [("F022", 1, 120), ("F023", 1, 100)])

    # Lunch
    if day == date(2025, 11, 8) or rng.random() < 0.95:
        dt = at(day, 12.5, 14.5)
        if day == date(2025, 11, 8) or rng.random() < (0.5 if weekend else 0.7):
            # one early fish order whose feedback records the "avoid" label
            fid = "F019" if day == date(2025, 11, 8) else choose(weights(LUNCH_DELIVERY))
            vid = FOOD[fid]["vendor_id"]
            qty = 2 if rng.random() < 0.06 else 1
            lines = [(fid, qty, FOOD[fid]["serving_size"])]
            if vid in SIDES and rng.random() < 0.3:
                lines.append((SIDES[vid], 1, FOOD[SIDES[vid]]["serving_size"]))
            add_order(day, dt, "lunch", "delivery_order", vid, lines)
        else:
            lines = [("F027", 1, 450)]
            if rng.random() < 0.4:
                lines.append(("F021", 1, 150))
            add_order(day, dt, "lunch", "home_meal", "V08", lines)

    # Snack
    if rng.random() < 0.6:
        dt = at(day, 16.5, 18.0)
        r = rng.random()
        if r < 0.55:
            lines = [("F031", 1, 150)]
            if rng.random() < 0.35:
                lines.append(("F033", 1, 140))
            elif rng.random() < 0.15:
                lines.append(("F034", 1, 100))
            meal = "snack" if rng.random() > 0.03 else ""
            add_order(day, dt, meal, "cafe_purchase", "V09", lines)
        elif r < 0.72:
            fid = choose({"F032": 4, "F036": 3, "F035": 2, "F037": 3})
            add_order(day, dt, "snack", "cafe_purchase", "V09", [(fid, 1, FOOD[fid]["serving_size"])])
        else:
            fid = choose({"F025": 4, "F024": 3, "F026": 3, "F022": 2})
            add_order(day, dt, "snack", "home_meal", "V08", [(fid, 1, FOOD[fid]["serving_size"])])

    # Dinner
    if rng.random() < 0.95:
        dt = at(day, 19.5, 21.5)
        r = rng.random()
        if r < (0.55 if weekend else 0.40):
            fid = choose(weights(DINNER_DELIVERY))
            vid = FOOD[fid]["vendor_id"]
            lines = [(fid, 2 if rng.random() < 0.08 else 1, FOOD[fid]["serving_size"])]
            if vid in SIDES and rng.random() < 0.25:
                lines.append((SIDES[vid], 1, FOOD[SIDES[vid]]["serving_size"]))
            add_order(day, dt, "dinner", "delivery_order", vid, lines)
        elif r < 0.88:
            lines = [("F027", 1, 450)]
            if rng.random() < 0.35:
                lines.append(("F021", 1, 150))
            add_order(day, dt, "dinner", "home_meal", "V08", lines)
        else:
            add_order(day, dt, "dinner", "home_meal", "V08", [("F030", 1, 300)])
    day += timedelta(days=1)

# A few explicit ratings for rarely ordered but well-liked foods, recorded via a survey
for fid, d, rating in [("F018", date(2026, 6, 14), 5), ("F038", date(2026, 7, 2), 4),
                       ("F010", date(2026, 8, 20), 5)]:
    feedback.append({"feedback_id": new_id("fb", "FB", 4), "user_id": USER_ID, "food_id": fid,
                     "order_id": "", "feedback_date": d.isoformat(), "rating": rating,
                     "preference_label": "liked", "comment": "In-app preference survey",
                     "would_buy_again": "yes", "serving_preference": "same"})

# --------------------------------------------------------------------------- health
health: list[dict] = []
hid = 0


def add_measure(d: date, indicator: str, value: float, unit: str, source: str, notes: str = "") -> None:
    global hid
    hid += 1
    health.append({"measurement_id": f"H{hid:04d}", "user_id": USER_ID, "measurement_date": d.isoformat(),
                   "indicator": indicator, "value": value, "unit": unit, "source": source, "notes": notes})


d = START + timedelta(days=(6 - START.weekday()) % 7)   # first Sunday
while d <= END:
    t = (d - START).days
    if not (date(2026, 3, 1) <= d <= date(2026, 3, 29)) and rng.random() > 0.12:
        w = 82.6 - 0.0115 * t + 0.6 * np.sin(t / 58) + rng.normal(0, 0.35)
        add_measure(d, "weight", round(float(w), 1), "kg", "home digital scale (synthetic)", "Morning, before breakfast")
    d += timedelta(days=7)

for m in range(12):
    md = date(2025, 11, 1) + timedelta(days=30 * m + int(rng.integers(0, 6)))
    if md > END:
        break
    add_measure(md, "waist_circumference", round(float(96.5 - 0.35 * m + rng.normal(0, 0.5)), 1), "cm",
                "tape measure at navel (synthetic)")
    if m != 4:   # one missed month
        add_measure(md, "systolic_bp", int(round(129 - 0.6 * m + rng.normal(0, 3))), "mmHg",
                    "home BP monitor (synthetic)", "Seated, average of 2 readings")
        add_measure(md, "diastolic_bp", int(round(85 - 0.45 * m + rng.normal(0, 2))), "mmHg",
                    "home BP monitor (synthetic)", "Seated, average of 2 readings")

for d, v in [(date(2025, 11, 10), 104), (date(2026, 2, 12), 102), (date(2026, 5, 18), 99), (date(2026, 8, 24), 97)]:
    add_measure(d, "fasting_glucose", v, "mg/dL", "laboratory report (synthetic)", "8+ hour fast")

# --------------------------------------------------------------------------- reference tables
users = [{"user_id": USER_ID, "display_name": "Synthetic Persona A", "sex": "male", "birth_year": 1995,
          "height_cm": 172, "activity_level": "sedentary", "is_synthetic": True}]

latest_weight = [h for h in health if h["indicator"] == "weight"][-1]["value"]
goals = [
    {"goal_id": "G01", "user_id": USER_ID, "goal_key": "protein", "goal_name": "Increase protein toward RDA",
     "nutrient": "protein_g", "direction": "at_least", "target_value": round(0.83 * latest_weight, 1),
     "unit": "g/day", "reference_source": "ICMR-NIN Nutrient Requirements for Indians (2020): protein RDA 0.83 g/kg body weight/day; multiplied by latest recorded weight",
     "reference_date": "2020", "is_active": True},
    {"goal_id": "G02", "user_id": USER_ID, "goal_key": "fiber", "goal_name": "Increase dietary fibre",
     "nutrient": "fiber_g", "direction": "at_least", "target_value": 30.0, "unit": "g/day",
     "reference_source": "Dietary Guidelines for Americans 2020-2025 / IOM Adequate Intake: 14 g fibre per 1,000 kcal (~30 g at 2,110 kcal)",
     "reference_date": "2020", "is_active": False},
    {"goal_id": "G03", "user_id": USER_ID, "goal_key": "calories", "goal_name": "Keep energy within estimated requirement",
     "nutrient": "calories_kcal", "direction": "at_most", "target_value": 2110.0, "unit": "kcal/day",
     "reference_source": "ICMR-NIN Nutrient Requirements for Indians (2020): estimated energy requirement, sedentary adult man (reference body weight 65 kg)",
     "reference_date": "2020", "is_active": False},
]

reference_ranges = [
    {"indicator": "bmi", "lower": 18.5, "upper": 24.9, "unit": "kg/m2",
     "source": "WHO adult BMI classification (normal 18.5-24.9). WHO expert consultation (2004) notes lower public-health action points (23) for Asian populations."},
    {"indicator": "fasting_glucose", "lower": 70, "upper": 99, "unit": "mg/dL",
     "source": "American Diabetes Association Standards of Care: fasting plasma glucose < 100 mg/dL is the normal range"},
    {"indicator": "systolic_bp", "lower": "", "upper": 119, "unit": "mmHg",
     "source": "2017 ACC/AHA guideline: normal blood pressure < 120 mmHg systolic"},
    {"indicator": "diastolic_bp", "lower": "", "upper": 79, "unit": "mmHg",
     "source": "2017 ACC/AHA guideline: normal blood pressure < 80 mmHg diastolic"},
    {"indicator": "waist_circumference", "lower": "", "upper": 89.9, "unit": "cm",
     "source": "IDF consensus (2006): ethnic-specific waist threshold for South Asian men >= 90 cm"},
    {"indicator": "fat_energy_pct", "lower": "", "upper": 30, "unit": "% of energy",
     "source": "WHO Healthy diet fact sheet: total fat should not exceed 30% of total energy intake"},
    {"indicator": "carb_energy_pct", "lower": 45, "upper": 65, "unit": "% of energy",
     "source": "IOM Acceptable Macronutrient Distribution Range: carbohydrate 45-65% of energy"},
]

# --------------------------------------------------------------------------- catalogue tables
vendors = [{"vendor_id": v["vendor_id"], "vendor_name": v["vendor_name"], "channel": v["channel"],
            "tax_rate": v["tax_rate"], "typical_delivery_fee_inr": v["delivery_fee"]} for v in VENDOR.values()]
foods = [{"food_id": f["food_id"], "food_name": f["name"], "category": f["category"], "role": f["role"],
          "vendor_id": f["vendor_id"], "default_serving_size": f["serving_size"], "serving_unit": f["unit"],
          "is_active": True} for f in FOOD.values()]
nutrition = [{"nutrition_id": f"N{f['food_id'][1:]}", "food_id": f["food_id"], "basis": f["basis"],
              "basis_quantity": f["basis_qty"], "basis_unit": f["unit"], "calories_kcal": f["kcal"],
              "protein_g": f["protein"], "carbs_g": f["carbs"], "fat_g": f["fat"],
              "fiber_g": "" if f["fiber"] is None else f["fiber"],
              "nutrition_source": "Synthetic estimate approximating typical published values (IFCT 2017 / USDA FoodData Central); not item-verified",
              "source_date": "2026-10-01"} for f in FOOD.values()]
meal_options = []
mo = 0
for fid, meal_types in MEAL_TYPES.items():
    f = FOOD[fid]
    kind = ("main_delivery" if f["role"] == "main" and VENDOR[f["vendor_id"]]["channel"] == "delivery"
            else "main_home" if f["vendor_id"] == "V08" and f["role"] == "main"
            else "pantry" if f["role"] == "pantry" else "other")
    if f["basis"] == "per_serving":
        price = price_on(fid, END)
    else:
        price = round(price_on(fid, END) * f["serving_size"] / 100, 2)
    source = ("estimated ingredient cost (synthetic)" if f["vendor_id"] == "V08" else
              "latest grocery price in synthetic history, prorated to serving" if f["role"] == "pantry" else
              "latest list price in synthetic order history")
    for mt in meal_types:
        mo += 1
        meal_options.append({"meal_option_id": f"MO{mo:03d}", "food_id": fid, "meal_type": mt,
                             "serving_size": f["serving_size"], "serving_unit": f["unit"],
                             "price_per_serving_inr": price, "allowed_servings": ALLOWED_SERVINGS[kind],
                             "availability_status": "listed_in_dataset", "price_source": source,
                             "price_date": END.isoformat()})

# --------------------------------------------------------------------------- inject raw quality issues
issues_log = []
by_food = {}
for it in items:
    by_food.setdefault(it["food_id"], []).append(it)

for fid, variants in RAW_NAME_VARIANTS.items():
    pool = by_food[fid]
    for idx in rng.choice(len(pool), size=min(10, len(pool)), replace=False):
        pool[idx]["food_name_raw"] = str(rng.choice(variants))
issues_log.append("food_name_raw variants for F001/F004/F013/F027 (up to 10 rows each)")

for fid in ("F001", "F013", "F004", "F027"):
    by_food[fid][-1]["food_id"] = ""
    by_food[fid][-1]["food_name_raw"] = RAW_NAME_VARIANTS[fid][0]
issues_log.append("4 order items with blank food_id (resolvable by name matching)")

g_items = [it for it in items if it["serving_unit"] == "g"]
for idx in rng.choice(len(g_items), size=25, replace=False):
    g_items[idx]["serving_unit"] = str(rng.choice(["G", "grams", "gm"]))
ml_items = [it for it in items if it["serving_unit"] == "ml"]
for idx in rng.choice(len(ml_items), size=5, replace=False):
    ml_items[idx]["serving_unit"] = "ML"
issues_log.append("30 inconsistent unit spellings (G, grams, gm, ML)")

delivery_orders = [o for o in orders if o["record_type"] == "delivery_order"]
bad = [("F013", 0), ("F006", -1), ("F999", 1)]
for (fid, qty), o in zip(bad, rng.choice(delivery_orders, size=3, replace=False)):
    items.append({"order_item_id": new_id("item", "I", 6), "order_id": o["order_id"], "food_id": fid,
                  "food_name_raw": "Unknown item" if fid == "F999" else FOOD[fid]["name"], "quantity": qty,
                  "serving_size": 350, "serving_unit": "g", "unit_price_inr": 180.0, "item_discount_inr": 0.0,
                  "line_total_inr": 180.0 * qty, "consumption_status": "unknown", "portion_consumed": ""})
issues_log.append("3 invalid order items (quantity 0, quantity -1, unknown food F999), not part of receipts")

for o in rng.choice(delivery_orders, size=2, replace=False):
    o["final_total_inr"] = round(o["final_total_inr"] + 50, 2)
issues_log.append("2 orders whose final_total does not equal the sum of their components")

items.extend(dict(items[i]) for i in rng.choice(len(items) - 3, size=3, replace=False))
orders.extend(dict(orders[i]) for i in rng.choice(len(orders), size=2, replace=False))
issues_log.append("3 duplicated order-item rows and 2 duplicated order rows")

fb_valid = list(feedback)
fb_valid[5]["rating"] = 6
fb_valid[17]["rating"] = ""
for idx in rng.choice(len(fb_valid), size=10, replace=False):
    if fb_valid[idx]["preference_label"] in ("liked", "disliked"):
        fb_valid[idx]["preference_label"] = str(rng.choice(
            ["Liked ", "LIKED", "like"] if fb_valid[idx]["preference_label"] == "liked" else ["dislike", "Disliked "]))
fb_valid[30]["order_id"] = "O99999"
issues_log.append("feedback: rating 6, missing rating, label spelling variants, 1 broken order link")

weights_rows = [h for h in health if h["indicator"] == "weight"]
weights_rows[20]["value"] = round(weights_rows[20]["value"] / 10, 2)
health.append(dict(health[3]))
issues_log.append("health: 1 implausible weight (decimal-shift typo), 1 duplicated measurement")

# --------------------------------------------------------------------------- write
RAW.mkdir(parents=True, exist_ok=True)


def write(name: str, rows: list[dict]) -> None:
    with open(RAW / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


write("users.csv", users)
write("vendors.csv", vendors)
write("foods.csv", foods)
write("food_nutrition.csv", nutrition)
write("meal_options.csv", meal_options)
write("orders.csv", orders)
write("order_items.csv", items)
write("food_feedback.csv", feedback)
write("health_measurements.csv", health)
write("nutrition_goals.csv", goals)
write("reference_ranges.csv", reference_ranges)

manifest = {
    "synthetic": True,
    "generator": "analysis/scripts/generate_synthetic_data.py",
    "seed": SEED, "period_start": START.isoformat(), "period_end": END.isoformat(),
    "row_counts": {"orders": len(orders), "order_items": len(items), "food_feedback": len(feedback),
                   "health_measurements": len(health), "foods": len(foods), "meal_options": len(meal_options)},
    "injected_quality_issues": issues_log,
}
(RAW / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
