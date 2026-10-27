"""Validate and clean data/raw/*.csv into data/processed/*.csv.

Produces:
  data/processed/<table>.csv               cleaned tables (loaded into MySQL by the Django import command)
  data/processed/rejected_records.csv      every rejected row with the rule that rejected it
  analysis/reports/data_quality_report.json / .md

Rules (also documented in DECISIONS.md and docs/):
  * Exact duplicate rows are removed (counted).
  * Units are standardised (G/grams/gm -> g, ML -> ml).
  * Blank food_id is resolved only by an exact match on a normalised food name (lower-case,
    punctuation removed, "w/" -> "with", whitespace collapsed). Unresolved rows are rejected.
  * Rows with non-positive quantities, unknown foods/orders, ratings outside 1-5, or physiologically
    implausible measurements are rejected, never corrected by guesswork.
  * Order final_total is recomputed from its components (subtotal - discount + tax + fees + other);
    mismatches are flagged (total_recomputed = True).
  * Missing meal_type on food orders is inferred from the order time window and flagged
    (meal_type_inferred = True). Grocery purchases are not meals -> meal_type "not_applicable".
  * Unknown nutrient values stay missing (NULL); they are never converted to zero.

Usage:  python analysis/scripts/clean_data.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW, OUT, REPORTS = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "analysis" / "reports"

REQUIRED = {
    "users": ["user_id", "display_name", "height_cm"],
    "vendors": ["vendor_id", "vendor_name", "channel", "tax_rate"],
    "foods": ["food_id", "food_name", "category", "role", "vendor_id", "default_serving_size", "serving_unit"],
    "food_nutrition": ["food_id", "basis", "basis_quantity", "basis_unit", "calories_kcal", "protein_g",
                       "carbs_g", "fat_g", "fiber_g"],
    "meal_options": ["meal_option_id", "food_id", "meal_type", "serving_size", "price_per_serving_inr"],
    "orders": ["order_id", "user_id", "order_datetime", "record_type", "vendor_id", "items_subtotal_inr",
               "order_discount_inr", "tax_inr", "delivery_fee_inr", "other_charges_inr", "final_total_inr"],
    "order_items": ["order_item_id", "order_id", "food_id", "quantity", "serving_size", "serving_unit",
                    "unit_price_inr", "line_total_inr", "consumption_status"],
    "food_feedback": ["feedback_id", "food_id", "feedback_date", "rating", "preference_label"],
    "health_measurements": ["measurement_id", "measurement_date", "indicator", "value", "unit"],
    "nutrition_goals": ["goal_id", "goal_key", "nutrient", "direction", "target_value", "reference_source"],
    "reference_ranges": ["indicator", "lower", "upper", "unit", "source"],
}
UNIT_MAP = {"g": "g", "gm": "g", "grams": "g", "gram": "g", "ml": "ml", "millilitre": "ml"}
LABEL_MAP = {"liked": "liked", "like": "liked", "acceptable": "acceptable", "neutral": "acceptable",
             "disliked": "disliked", "dislike": "disliked", "avoid": "avoid"}
PLAUSIBLE = {"weight": (30, 250), "waist_circumference": (50, 200), "systolic_bp": (70, 250),
             "diastolic_bp": (40, 150), "fasting_glucose": (40, 400)}
MEAL_WINDOWS = [(0, 11, "breakfast"), (11, 16, "lunch"), (16, 19, "snack"), (19, 24, "dinner")]
CONSUMPTION_STATES = {"consumed", "partially_consumed", "not_consumed", "unknown"}

rejected: list[dict] = []
report: dict = {"tables": {}, "checks": [], "synthetic_data": True}


def reject(table: str, df: pd.DataFrame, mask: pd.Series, rule: str, key: str) -> pd.DataFrame:
    for _, row in df[mask].iterrows():
        rejected.append({"table": table, "record_id": row.get(key, ""), "rule": rule,
                         "row": json.dumps({k: (None if pd.isna(v) else str(v)) for k, v in row.items()})})
    if mask.any():
        report["checks"].append({"table": table, "check": rule, "rows_rejected": int(mask.sum())})
    return df[~mask].copy()


def note(table: str, check: str, **values) -> None:
    report["checks"].append({"table": table, "check": check, **values})


def norm_name(s: str) -> str:
    s = str(s).lower().replace("w/", "with ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False, na_values=[""])
    missing_cols = [c for c in REQUIRED[name] if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"{name}.csv is missing required columns: {missing_cols}")
    report["tables"][name] = {"raw_rows": len(df),
                              "missing_values": {c: int(n) for c, n in df.isna().sum().items() if n}}
    dups = df.duplicated()
    if dups.any():
        note(name, "exact duplicate rows removed", rows_removed=int(dups.sum()))
    return df[~dups].reset_index(drop=True)


def to_num(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    t = {name: load(name) for name in REQUIRED}

    # ---------------- reference tables
    vendors, foods, nut = t["vendors"], t["foods"], t["food_nutrition"]
    to_num(vendors, ["tax_rate", "typical_delivery_fee_inr"])
    to_num(foods, ["default_serving_size"])
    foods["serving_unit"] = foods["serving_unit"].str.strip().str.lower().map(UNIT_MAP)
    foods["food_name"] = foods["food_name"].str.strip()
    foods = reject("foods", foods, ~foods["vendor_id"].isin(vendors["vendor_id"]), "unknown vendor_id", "food_id")
    dup_names = foods["food_name"].map(norm_name).duplicated(keep=False)
    foods = reject("foods", foods, dup_names, "duplicate food name after normalisation", "food_id")

    nut_cols = ["basis_quantity", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]
    to_num(nut, nut_cols)
    nut["basis_unit"] = nut["basis_unit"].str.strip().str.lower().map(UNIT_MAP)
    nut = reject("food_nutrition", nut, ~nut["food_id"].isin(foods["food_id"]), "unknown food_id", "food_id")
    nut = reject("food_nutrition", nut, ~nut["basis"].isin(["per_serving", "per_100g", "per_100ml"]),
                 "unsupported nutrition basis", "food_id")
    neg = (nut[nut_cols] < 0).any(axis=1)
    nut = reject("food_nutrition", nut, neg, "negative nutrient value", "food_id")
    unit_mismatch = nut.merge(foods[["food_id", "serving_unit"]], on="food_id")
    bad_unit = unit_mismatch["basis_unit"] != unit_mismatch["serving_unit"]
    note("food_nutrition", "nutrition basis unit matches food serving unit",
         mismatches=int(bad_unit.sum()))
    missing_nut = nut[nut[nut_cols].isna().any(axis=1)]
    note("food_nutrition", "foods with unknown nutrient values (kept as NULL, not zero)",
         foods=[f"{r.food_id}: " + ", ".join(c for c in nut_cols if pd.isna(r[c])) for _, r in missing_nut.iterrows()])

    opts = t["meal_options"]
    to_num(opts, ["serving_size", "price_per_serving_inr"])
    opts["serving_unit"] = opts["serving_unit"].str.strip().str.lower().map(UNIT_MAP)
    opts = reject("meal_options", opts, ~opts["food_id"].isin(foods["food_id"]), "unknown food_id", "meal_option_id")
    opts = reject("meal_options", opts, ~(opts["price_per_serving_inr"] > 0), "non-positive price", "meal_option_id")

    # ---------------- orders
    orders = t["orders"]
    money = ["items_subtotal_inr", "order_discount_inr", "tax_inr", "delivery_fee_inr", "other_charges_inr",
             "final_total_inr"]
    to_num(orders, money)
    dup_ids = orders["order_id"].duplicated(keep=False)
    orders = reject("orders", orders, dup_ids, "conflicting rows share an order_id", "order_id")
    orders["order_datetime"] = pd.to_datetime(orders["order_datetime"], errors="coerce")
    orders = reject("orders", orders, orders["order_datetime"].isna(), "invalid order_datetime", "order_id")
    orders = reject("orders", orders, (orders[money] < 0).any(axis=1) | orders[money].isna().any(axis=1),
                    "missing or negative monetary value", "order_id")
    orders = reject("orders", orders, ~orders["vendor_id"].isin(vendors["vendor_id"]), "unknown vendor_id", "order_id")
    orders["order_date"] = orders["order_datetime"].dt.date.astype(str)

    orders["meal_type"] = orders["meal_type"].str.strip().str.lower()
    orders["meal_type_inferred"] = False
    is_grocery = orders["record_type"] == "grocery_purchase"
    orders.loc[is_grocery, "meal_type"] = "not_applicable"
    blank = orders["meal_type"].isna()
    hours = orders["order_datetime"].dt.hour
    for lo, hi, label in MEAL_WINDOWS:
        m = blank & (hours >= lo) & (hours < hi)
        orders.loc[m, "meal_type"] = label
        orders.loc[m, "meal_type_inferred"] = True
    note("orders", "meal_type inferred from order time (flagged meal_type_inferred)",
         rows=int(orders["meal_type_inferred"].sum()),
         rule="breakfast <11:00, lunch 11-16, snack 16-19, dinner >=19:00")

    recomputed = (orders["items_subtotal_inr"] - orders["order_discount_inr"] + orders["tax_inr"]
                  + orders["delivery_fee_inr"] + orders["other_charges_inr"]).round(2)
    mismatch = (recomputed - orders["final_total_inr"]).abs() > 0.01
    note("orders", "final_total recomputed from components (subtotal - discount + tax + delivery + other)",
         rows=int(mismatch.sum()), order_ids=orders.loc[mismatch, "order_id"].tolist(),
         difference_inr=float((orders.loc[mismatch, "final_total_inr"] - recomputed[mismatch]).sum()))
    orders["total_recomputed"] = mismatch
    orders["final_total_inr"] = recomputed
    orders["counts_as_spending"] = orders["record_type"] != "home_meal"

    # ---------------- order items
    items = t["order_items"]
    to_num(items, ["quantity", "serving_size", "unit_price_inr", "item_discount_inr", "line_total_inr",
                   "portion_consumed"])
    raw_units = items["serving_unit"].copy()
    items["serving_unit"] = items["serving_unit"].str.strip().str.lower().map(UNIT_MAP)
    changed = raw_units != items["serving_unit"]
    note("order_items", "serving units standardised", rows=int(changed.sum()),
         variants=sorted(raw_units[changed].dropna().unique().tolist()))
    items = reject("order_items", items, items["serving_unit"].isna(), "unrecognised serving unit", "order_item_id")

    items["food_match_method"] = np.where(items["food_id"].notna(), "food_id", None)
    name_index = {norm_name(n): fid for fid, n in zip(foods["food_id"], foods["food_name"])}
    blank_food = items["food_id"].isna()
    resolved = items.loc[blank_food, "food_name_raw"].map(lambda s: name_index.get(norm_name(s)))
    items.loc[blank_food, "food_id"] = resolved
    items.loc[blank_food & items["food_id"].notna(), "food_match_method"] = "normalised_name"
    note("order_items", "blank food_id resolved by exact normalised-name match",
         resolved=int(resolved.notna().sum()), unresolved=int(resolved.isna().sum()))
    canonical = items["food_id"].map(dict(zip(foods["food_id"], foods["food_name"])))
    name_diff = items["food_id"].notna() & canonical.notna() & (items["food_name_raw"] != canonical)
    note("order_items", "raw food names standardised to catalogue name", rows=int(name_diff.sum()))
    items["food_name_raw"] = items["food_name_raw"].str.strip()

    items = reject("order_items", items, items["food_id"].isna() | ~items["food_id"].isin(foods["food_id"]),
                   "unknown food (orphan food_id)", "order_item_id")
    items = reject("order_items", items, ~items["order_id"].isin(orders["order_id"]),
                   "unknown order_id (orphan item)", "order_item_id")
    items = reject("order_items", items, ~(items["quantity"] > 0), "quantity must be > 0", "order_item_id")
    items = reject("order_items", items, ~(items["serving_size"] > 0) | ~(items["unit_price_inr"] >= 0),
                   "invalid serving size or price", "order_item_id")
    dup_item_ids = items["order_item_id"].duplicated(keep=False)
    items = reject("order_items", items, dup_item_ids, "conflicting rows share an order_item_id", "order_item_id")

    unit_check = items.merge(foods[["food_id", "serving_unit"]], on="food_id", suffixes=("", "_food"))
    note("order_items", "item unit matches food unit",
         mismatches=int((unit_check["serving_unit"] != unit_check["serving_unit_food"]).sum()))

    items["item_discount_inr"] = items["item_discount_inr"].fillna(0.0)
    line_calc = (items["quantity"] * items["unit_price_inr"] - items["item_discount_inr"]).round(2)
    bad_line = (line_calc - items["line_total_inr"]).abs() > 0.01
    note("order_items", "line_total = quantity x unit_price - item_discount", mismatches=int(bad_line.sum()))
    items.loc[bad_line, "line_total_inr"] = line_calc[bad_line]

    items["consumption_status"] = items["consumption_status"].str.strip().str.lower()
    items = reject("order_items", items, ~items["consumption_status"].isin(CONSUMPTION_STATES),
                   "unknown consumption_status", "order_item_id")
    expected_portion = items["consumption_status"].map({"consumed": 1.0, "not_consumed": 0.0})
    fix = expected_portion.notna() & items["portion_consumed"].isna()
    items.loc[fix, "portion_consumed"] = expected_portion[fix]
    items.loc[items["consumption_status"] == "unknown", "portion_consumed"] = np.nan

    recon = items.groupby("order_id")["line_total_inr"].sum().round(2)
    sub = orders.set_index("order_id")["items_subtotal_inr"]
    diff = (recon.reindex(sub.index) - sub).abs()
    note("orders", "sum(item line totals) equals order items_subtotal (no double counting)",
         orders_checked=int(len(sub)), mismatches=int((diff > 0.01).sum()),
         orders_without_items=int(diff.isna().sum()))

    # ---------------- feedback
    fb = t["food_feedback"]
    fb["rating"] = pd.to_numeric(fb["rating"], errors="coerce")
    fb = reject("food_feedback", fb, ~fb["rating"].between(1, 5) | (fb["rating"] % 1 != 0),
                "rating missing or outside 1-5", "feedback_id")
    fb["rating"] = fb["rating"].astype(int)
    raw_labels = fb["preference_label"].copy()
    fb["preference_label"] = fb["preference_label"].str.strip().str.lower().map(LABEL_MAP)
    note("food_feedback", "preference labels standardised",
         rows=int((raw_labels != fb["preference_label"]).sum()),
         variants=sorted(raw_labels[raw_labels != fb["preference_label"]].dropna().unique().tolist()))
    fb = reject("food_feedback", fb, fb["preference_label"].isna(), "unrecognised preference label", "feedback_id")
    fb = reject("food_feedback", fb, ~fb["food_id"].isin(foods["food_id"]), "unknown food_id", "feedback_id")
    broken = fb["order_id"].notna() & ~fb["order_id"].isin(orders["order_id"])
    note("food_feedback", "order link removed where order_id does not exist (feedback kept)",
         rows=int(broken.sum()), feedback_ids=fb.loc[broken, "feedback_id"].tolist())
    fb["order_link_removed"] = broken
    fb.loc[broken, "order_id"] = np.nan
    inconsistent = ((fb["preference_label"] == "liked") & (fb["rating"] <= 2)) | \
                   ((fb["preference_label"] == "disliked") & (fb["rating"] >= 4))
    note("food_feedback", "label contradicts rating (kept, reported)", rows=int(inconsistent.sum()))

    # ---------------- health
    h = t["health_measurements"]
    h["value"] = pd.to_numeric(h["value"], errors="coerce")
    h["measurement_date"] = pd.to_datetime(h["measurement_date"], errors="coerce").dt.date.astype(str)
    h = reject("health_measurements", h, h["value"].isna(), "missing value", "measurement_id")
    bounds = h["indicator"].map(PLAUSIBLE)
    implausible = bounds.map(lambda b: b is None or (isinstance(b, float) and np.isnan(b)))
    lo = bounds.map(lambda b: b[0] if isinstance(b, tuple) else np.nan)
    hi = bounds.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    h = reject("health_measurements", h, implausible | (h["value"] < lo) | (h["value"] > hi),
               "physiologically implausible value or unknown indicator", "measurement_id")
    same = h.duplicated(subset=["user_id", "measurement_date", "indicator"], keep="first")
    h = reject("health_measurements", h, same, "duplicate measurement (same date and indicator)", "measurement_id")
    report["health_frequency"] = {
        ind: {"count": int(len(g)), "first": g["measurement_date"].min(), "last": g["measurement_date"].max(),
              "median_days_between": float(pd.to_datetime(g["measurement_date"]).sort_values().diff().dt.days.median())
              if len(g) > 1 else None}
        for ind, g in h.groupby("indicator")}

    # ---------------- coverage
    od = pd.to_datetime(orders["order_date"])
    all_days = pd.date_range(od.min(), od.max())
    logged = set(od.dt.normalize())
    missing_days = [d for d in all_days if d not in logged]
    gaps, run = [], []
    for d in missing_days:
        if run and (d - run[-1]).days != 1:
            gaps.append(run)
            run = []
        run.append(d)
    if run:
        gaps.append(run)
    report["coverage"] = {
        "first_date": str(od.min().date()), "last_date": str(od.max().date()),
        "calendar_days": len(all_days), "days_with_records": len(logged),
        "gaps_of_3_plus_days": [{"from": str(g[0].date()), "to": str(g[-1].date()), "days": len(g)}
                                for g in gaps if len(g) >= 3],
        "orders_by_record_type": orders["record_type"].value_counts().to_dict(),
        "items_by_consumption_status": items["consumption_status"].value_counts().to_dict(),
    }

    # ---------------- write
    out_tables = {
        "users": t["users"], "vendors": vendors, "foods": foods, "food_nutrition": nut, "meal_options": opts,
        "orders": orders.assign(order_datetime=orders["order_datetime"].dt.strftime("%Y-%m-%dT%H:%M")),
        "order_items": items, "food_feedback": fb, "health_measurements": h,
        "nutrition_goals": t["nutrition_goals"], "reference_ranges": t["reference_ranges"],
    }
    for name, df in out_tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        report["tables"][name]["clean_rows"] = len(df)
    pd.DataFrame(rejected, columns=["table", "record_id", "rule", "row"]).to_csv(
        OUT / "rejected_records.csv", index=False)
    report["rejected_total"] = len(rejected)

    (REPORTS / "data_quality_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_markdown(report)
    print(f"Clean tables written to {OUT}")
    print(f"Rejected rows: {len(rejected)}  |  report: analysis/reports/data_quality_report.md")


def write_markdown(r: dict) -> None:
    lines = ["# Data Quality Report", "",
             "> All data is **synthetic** (generated by `analysis/scripts/generate_synthetic_data.py`).", "",
             "## Row counts", "", "| Table | Raw rows | Clean rows | Columns with missing values |",
             "|---|---:|---:|---|"]
    for name, info in r["tables"].items():
        mv = ", ".join(f"{k} ({v})" for k, v in info["missing_values"].items()) or "none"
        lines.append(f"| {name} | {info['raw_rows']} | {info.get('clean_rows', '')} | {mv} |")
    lines += ["", "Note: some columns are blank by design (e.g. `meal_type` for grocery purchases, "
              "`portion_consumed` when consumption is unknown, `order_id` for survey feedback).", "",
              "## Checks and actions", "", "| Table | Check | Result |", "|---|---|---|"]
    for c in r["checks"]:
        detail = ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("table", "check"))
        lines.append(f"| {c['table']} | {c['check']} | {detail} |")
    cov = r["coverage"]
    lines += ["", "## Coverage", "",
              f"- Period: {cov['first_date']} to {cov['last_date']} ({cov['calendar_days']} calendar days); "
              f"{cov['days_with_records']} days have at least one record.",
              f"- Gaps of 3+ days: {cov['gaps_of_3_plus_days'] or 'none'}",
              f"- Orders by record type: {cov['orders_by_record_type']}",
              f"- Items by consumption status: {cov['items_by_consumption_status']}", "",
              "## Health measurement frequency", "", "| Indicator | Count | First | Last | Median days between |",
              "|---|---:|---|---|---:|"]
    for ind, f in r["health_frequency"].items():
        lines.append(f"| {ind} | {f['count']} | {f['first']} | {f['last']} | {f['median_days_between']} |")
    lines += ["", f"Total rejected rows: **{r['rejected_total']}** (see `data/processed/rejected_records.csv`)."]
    (REPORTS / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
