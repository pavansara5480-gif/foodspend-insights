"""DataFrame analytics shared by the API (data loaded from MySQL) and notebooks (data loaded from CSV).

Conventions
-----------
* Spending  = sum of order final_total for record types in SPENDING_RECORD_TYPES (order-level, so
  charges are never multiplied by the number of items). Home meals carry an estimated ingredient cost
  that is reported separately and never added to spending.
* Category/food spending uses item line totals; order-level charges (tax + delivery + other - discount)
  are shown as their own row so the breakdown reconciles to total spending.
* Nutrition "purchased" = what was bought. Nutrition "consumed" = purchased x portion_consumed and is
  only available where consumption was recorded. Grocery purchases have unknown consumption; pantry food
  that was eaten is logged separately as home meals.
* Unknown nutrient values stay NaN and are reported, never filled with zero.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .constants import (NUTRIENTS, SPENDING_RECORD_TYPES, STATUS_INSUFFICIENT)
from .formulas import goal_status, pct


@dataclass
class Dataset:
    users: pd.DataFrame
    vendors: pd.DataFrame
    foods: pd.DataFrame
    nutrition: pd.DataFrame
    meal_options: pd.DataFrame
    orders: pd.DataFrame
    items: pd.DataFrame
    feedback: pd.DataFrame
    health: pd.DataFrame
    goals: pd.DataFrame
    ranges: pd.DataFrame


def load_processed(directory: str | Path) -> Dataset:
    d = Path(directory)
    r = lambda n: pd.read_csv(d / f"{n}.csv")  # noqa: E731
    ds = Dataset(users=r("users"), vendors=r("vendors"), foods=r("foods"), nutrition=r("food_nutrition"),
                 meal_options=r("meal_options"), orders=r("orders"), items=r("order_items"),
                 feedback=r("food_feedback"), health=r("health_measurements"), goals=r("nutrition_goals"), ranges=r("reference_ranges"))
    return normalise(ds)


def normalise(ds: Dataset) -> Dataset:
    """Coerce types so CSV- and database-loaded datasets behave identically."""
    o = ds.orders.copy()
    o["order_datetime"] = pd.to_datetime(o["order_datetime"])
    o["order_date"] = pd.to_datetime(o["order_date"])
    for c in ["items_subtotal_inr", "order_discount_inr", "tax_inr", "delivery_fee_inr", "other_charges_inr",
              "final_total_inr"]:
        o[c] = o[c].astype(float)
    it = ds.items.copy()
    for c in ["quantity", "serving_size", "unit_price_inr", "item_discount_inr", "line_total_inr",
              "portion_consumed"]:
        it[c] = pd.to_numeric(it[c], errors="coerce").astype(float)
    nut = ds.nutrition.copy()
    for c in NUTRIENTS + ["basis_quantity"]:
        nut[c] = pd.to_numeric(nut[c], errors="coerce").astype(float)
    fb = ds.feedback.copy()
    fb["feedback_date"] = pd.to_datetime(fb["feedback_date"])
    fb["rating"] = fb["rating"].astype(int)
    h = ds.health.copy()
    h["measurement_date"] = pd.to_datetime(h["measurement_date"])
    h["value"] = h["value"].astype(float)
    return replace(ds, orders=o, items=it, nutrition=nut, feedback=fb, health=h)


def filter_period(ds: Dataset, start=None, end=None) -> Dataset:
    """Restrict orders/items/feedback/health to [start, end] (inclusive dates)."""
    if start is None and end is None:
        return ds
    start = pd.Timestamp(start) if start is not None else pd.Timestamp.min
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.max
    o = ds.orders[(ds.orders["order_date"] >= start) & (ds.orders["order_date"] <= end)]
    return replace(
        ds, orders=o, items=ds.items[ds.items["order_id"].isin(o["order_id"])],
        feedback=ds.feedback[(ds.feedback["feedback_date"] >= start) & (ds.feedback["feedback_date"] <= end)],
        health=ds.health[(ds.health["measurement_date"] >= start) & (ds.health["measurement_date"] <= end)])


def _round(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    return df.round(n)


# ----------------------------------------------------------------------------- spending
def spending_orders(ds: Dataset) -> pd.DataFrame:
    return ds.orders[ds.orders["record_type"].isin(SPENDING_RECORD_TYPES)]


def spending_summary(ds: Dataset) -> dict:
    so = spending_orders(ds)
    homes = ds.orders[ds.orders["record_type"] == "home_meal"]
    total = float(so["final_total_inr"].sum())
    n = int(len(so))
    days = int((ds.orders["order_date"].max() - ds.orders["order_date"].min()).days + 1) if len(ds.orders) else 0
    food_orders = so[so["record_type"] != "grocery_purchase"]
    return {
        "period_start": ds.orders["order_date"].min().date().isoformat() if len(ds.orders) else None,
        "period_end": ds.orders["order_date"].max().date().isoformat() if len(ds.orders) else None,
        "period_days": days,
        "total_spending_inr": round(total, 2),
        "transactions": n,
        "average_transaction_value_inr": round(total / n, 2) if n else None,
        "food_orders": int(len(food_orders)),
        "average_food_order_value_inr": round(float(food_orders["final_total_inr"].mean()), 2) if len(food_orders) else None,
        "average_monthly_spending_inr": round(total / days * 30.44, 2) if days else None,
        "components_inr": {
            "items_subtotal": round(float(so["items_subtotal_inr"].sum()), 2),
            "discounts": round(float(so["order_discount_inr"].sum()), 2),
            "tax": round(float(so["tax_inr"].sum()), 2),
            "delivery_fees": round(float(so["delivery_fee_inr"].sum()), 2),
            "other_charges": round(float(so["other_charges_inr"].sum()), 2),
        },
        "by_record_type": _round(so.groupby("record_type")["final_total_inr"].agg(["sum", "count"])
                                 .rename(columns={"sum": "spending_inr", "count": "transactions"})
                                 .reset_index()).to_dict("records"),
        "home_meals_logged": int(len(homes)),
        "home_meals_estimated_ingredient_cost_inr": round(float(homes["final_total_inr"].sum()), 2),
        "formula": "spending = sum(final_total) over delivery, cafe and grocery transactions; "
                   "final_total = items subtotal - discount + tax + delivery fee + other charges. "
                   "Home-meal ingredient costs are estimates and excluded.",
    }


def spending_by_month(ds: Dataset) -> pd.DataFrame:
    so = spending_orders(ds).assign(month=lambda d: d["order_date"].dt.to_period("M").astype(str))
    pv = so.pivot_table(index="month", columns="record_type", values="final_total_inr", aggfunc="sum",
                        fill_value=0.0)
    for c in SPENDING_RECORD_TYPES:
        if c not in pv:
            pv[c] = 0.0
    pv["total"] = pv[list(SPENDING_RECORD_TYPES)].sum(axis=1)
    pv["transactions"] = so.groupby("month").size()
    return _round(pv.reset_index())


def spending_by(ds: Dataset, dimension: str) -> pd.DataFrame:
    so = spending_orders(ds)
    if dimension == "vendor":
        so = so.merge(ds.vendors[["vendor_id", "vendor_name"]], on="vendor_id", how="left", validate="m:1")
        key = "vendor_name"
    elif dimension in ("meal_type", "record_type"):
        key = dimension
    else:
        raise ValueError("dimension must be vendor, meal_type or record_type")
    g = so.groupby(key)["final_total_inr"].agg(["sum", "count", "mean"]).rename(
        columns={"sum": "spending_inr", "count": "transactions", "mean": "average_inr"})
    g["share_pct"] = g["spending_inr"] / g["spending_inr"].sum() * 100
    return _round(g.sort_values("spending_inr", ascending=False).reset_index().rename(columns={key: "label"}))


def spending_by_category(ds: Dataset) -> pd.DataFrame:
    so = spending_orders(ds)
    it = ds.items[ds.items["order_id"].isin(so["order_id"])].merge(
        ds.foods[["food_id", "category"]], on="food_id", how="left", validate="m:1")
    g = it.groupby("category")["line_total_inr"].sum().rename("spending_inr").reset_index().rename(
        columns={"category": "label"})
    charges = float((so["tax_inr"] + so["delivery_fee_inr"] + so["other_charges_inr"]
                     - so["order_discount_inr"]).sum())
    g = g.sort_values("spending_inr", ascending=False)
    g = pd.concat([g, pd.DataFrame([{"label": "Order-level charges (tax + fees - discounts)",
                                     "spending_inr": charges}])], ignore_index=True)
    g["share_pct"] = g["spending_inr"] / g["spending_inr"].sum() * 100
    return _round(g)


def purchase_frequency(ds: Dataset, top: int | None = 15) -> pd.DataFrame:
    """Purchase events per food from spending transactions (not proof of liking or consumption)."""
    so = spending_orders(ds)
    it = ds.items[ds.items["order_id"].isin(so["order_id"])]
    g = it.groupby("food_id").agg(purchase_events=("order_id", "nunique"), quantity=("quantity", "sum"),
                                  spending_inr=("line_total_inr", "sum"))
    g = g.merge(ds.foods.set_index("food_id")[["food_name", "category"]], left_index=True, right_index=True)
    g = g.sort_values(["purchase_events", "spending_inr"], ascending=False).reset_index()
    return _round(g.head(top) if top else g)


def meal_source_pattern(ds: Dataset) -> pd.DataFrame:
    """How each meal type is sourced (delivery / cafe / home), counted per logged meal."""
    m = ds.orders[ds.orders["record_type"] != "grocery_purchase"]
    pv = pd.crosstab(m["meal_type"], m["record_type"])
    return pv.reset_index()


# ----------------------------------------------------------------------------- nutrition
def item_nutrition(ds: Dataset) -> pd.DataFrame:
    """One row per order item with purchased and consumed nutrient estimates.

    amount   = quantity x serving_size  (in the item's unit)
    purchased nutrient = amount / basis_quantity x value per basis
    consumed nutrient  = purchased nutrient x portion_consumed  (NaN when consumption is unknown)
    """
    it = ds.items.merge(ds.nutrition[["food_id", "basis_quantity", "basis_unit"] + NUTRIENTS],
                        on="food_id", how="left", validate="m:1")
    it = it.merge(ds.orders[["order_id", "order_date", "meal_type", "record_type"]], on="order_id",
                  how="left", validate="m:1")
    it = it.merge(ds.foods[["food_id", "food_name", "category"]], on="food_id", how="left", validate="m:1")
    unit_ok = it["serving_unit"] == it["basis_unit"]
    factor = np.where(unit_ok, it["quantity"] * it["serving_size"] / it["basis_quantity"], np.nan)
    for n in NUTRIENTS:
        it[f"purchased_{n}"] = it[n] * factor
        it[f"consumed_{n}"] = it[f"purchased_{n}"] * it["portion_consumed"]
    it["unit_mismatch"] = ~unit_ok
    return it


def daily_intake(ds: Dataset) -> pd.DataFrame:
    """Logged consumed intake per day (meal records only; grocery purchases excluded)."""
    it = item_nutrition(ds)
    meals = it[it["record_type"] != "grocery_purchase"]
    cols = [f"consumed_{n}" for n in NUTRIENTS]
    g = meals.groupby("order_date")[cols].sum(min_count=1)
    g.columns = NUTRIENTS
    g["meals_logged"] = meals.groupby("order_date")["order_id"].nunique()
    g["items_unknown_consumption"] = meals.groupby("order_date")["portion_consumed"].apply(lambda s: s.isna().sum())
    g["items_unknown_fiber"] = meals.groupby("order_date")["fiber_g"].apply(lambda s: s.isna().sum())
    return g.reset_index()


def nutrition_summary(ds: Dataset, goals: pd.DataFrame | None = None) -> dict:
    """Average daily logged intake over the dataset period, compared with documented targets."""
    goals = ds.goals if goals is None else goals
    it = item_nutrition(ds)
    meals = it[it["record_type"] != "grocery_purchase"]
    daily = daily_intake(ds)
    period_days = int((ds.orders["order_date"].max() - ds.orders["order_date"].min()).days + 1) if len(ds.orders) else 0
    days_logged = int(len(daily))
    coverage = days_logged / period_days if period_days else 0
    avg = {n: (round(float(daily[n].mean()), 1) if days_logged and daily[n].notna().any() else None)
           for n in NUTRIENTS}

    rows = []
    for g in goals.to_dict("records"):
        value = avg.get(g["nutrient"])
        status = goal_status(value, g["direction"], target=float(g["target_value"]))
        if coverage < 0.5:
            status = STATUS_INSUFFICIENT
        rows.append({"goal_key": g["goal_key"], "goal_name": g["goal_name"], "nutrient": g["nutrient"],
                     "direction": g["direction"], "target": float(g["target_value"]), "unit": g["unit"],
                     "average_logged": value, "pct_of_target": pct(value, float(g["target_value"])),
                     "status": status, "reference_source": g["reference_source"]})

    energy = {}
    if avg["calories_kcal"]:
        energy = {"fat_energy_pct": round(avg["fat_g"] * 9 / avg["calories_kcal"] * 100, 1),
                  "carb_energy_pct": round(avg["carbs_g"] * 4 / avg["calories_kcal"] * 100, 1),
                  "protein_energy_pct": round(avg["protein_g"] * 4 / avg["calories_kcal"] * 100, 1)}
    ranges = []
    for r in ds.ranges.to_dict("records"):
        if r["indicator"] in energy:
            lo = None if pd.isna(r["lower"]) else float(r["lower"])
            hi = None if pd.isna(r["upper"]) else float(r["upper"])
            ranges.append({"indicator": r["indicator"], "value": energy[r["indicator"]], "lower": lo, "upper": hi,
                           "unit": r["unit"], "status": goal_status(energy[r["indicator"]], "range", lower=lo, upper=hi),
                           "reference_source": r["source"]})

    purchased = {n: round(float(it[f"purchased_{n}"].sum()), 1) for n in NUTRIENTS}
    return {
        "basis": "Logged consumption (meal records x portion consumed). Days without logs are excluded; "
                 "unlogged food is not represented, so averages are likely underestimates.",
        "period_days": period_days, "days_logged": days_logged, "logging_coverage_pct": round(coverage * 100, 1),
        "average_daily_logged": avg, "goals": rows, "energy_distribution": ranges,
        "completeness": {
            "meal_items": int(len(meals)),
            "meal_items_unknown_consumption": int(meals["portion_consumed"].isna().sum()),
            "meal_items_unknown_fiber": int(meals["fiber_g"].isna().sum()),
            "foods_with_unknown_nutrients": sorted(ds.nutrition.loc[ds.nutrition[NUTRIENTS].isna().any(axis=1),
                                                                    "food_id"].tolist()),
            "grocery_items_consumption_unknown": int((it["record_type"] == "grocery_purchase").sum()),
        },
        "purchased_totals_all_records": purchased,
    }


def nutrition_trend(ds: Dataset, freq: str = "M") -> pd.DataFrame:
    """Average daily logged intake per week ("W") or month ("M") over logged days."""
    daily = daily_intake(ds)
    if daily.empty:
        return daily
    key = daily["order_date"].dt.to_period(freq).astype(str)
    g = daily.groupby(key)[NUTRIENTS].mean()
    g["days_logged"] = daily.groupby(key).size()
    return _round(g.reset_index().rename(columns={"order_date": "period"}), 1)


# ----------------------------------------------------------------------------- preferences
def preference_table(ds: Dataset) -> pd.DataFrame:
    """Explicit feedback per food next to (separately reported) purchase and consumption counts."""
    fb = ds.feedback.sort_values(["feedback_date", "feedback_id"])
    g = fb.groupby("food_id").agg(n_ratings=("rating", "size"), mean_rating=("rating", "mean"),
                                  latest_label=("preference_label", "last"),
                                  latest_feedback_date=("feedback_date", "last"))
    dist = fb.pivot_table(index="food_id", columns="rating", values="feedback_id", aggfunc="count", fill_value=0)
    dist = dist.reindex(columns=range(1, 6), fill_value=0)
    dist.columns = [f"rating_{c}" for c in dist.columns]
    so = spending_orders(ds)
    bought = ds.items[ds.items["order_id"].isin(so["order_id"])].groupby("food_id")["order_id"].nunique()
    eaten = ds.items[ds.items["consumption_status"].isin(["consumed", "partially_consumed"])] \
        .groupby("food_id")["order_id"].nunique()
    t = ds.foods.set_index("food_id")[["food_name", "category"]].join(g).join(dist)
    t["purchase_events"] = bought.reindex(t.index).fillna(0).astype(int)
    t["logged_eaten_events"] = eaten.reindex(t.index).fillna(0).astype(int)
    t["n_ratings"] = t["n_ratings"].fillna(0).astype(int)
    t[[c for c in dist.columns]] = t[[c for c in dist.columns]].fillna(0).astype(int)
    t["preference_group"] = t["latest_label"].map(
        {"liked": "Positive", "acceptable": "Neutral", "disliked": "Negative", "avoid": "Negative (avoid)"}
    ).fillna("No feedback")
    t["mean_rating"] = t["mean_rating"].round(2)
    t["latest_feedback_date"] = t["latest_feedback_date"].dt.date.astype(str).replace("NaT", None)
    return t.reset_index().sort_values(["n_ratings", "mean_rating"], ascending=False)


def preference_summary(ds: Dataset) -> dict:
    t = preference_table(ds)
    rated = t[t["n_ratings"] > 0]
    corr = None
    if len(rated) >= 5:
        ranks = rated[["mean_rating", "purchase_events"]].rank()  # Spearman = Pearson on ranks
        corr = round(float(ranks["mean_rating"].corr(ranks["purchase_events"])), 2)
    return {
        "feedback_records": int(len(ds.feedback)),
        "foods_rated": int(len(rated)),
        "average_rating": round(float(ds.feedback["rating"].mean()), 2) if len(ds.feedback) else None,
        "rating_distribution": {int(k): int(v) for k, v in ds.feedback["rating"].value_counts().sort_index().items()},
        "groups": t["preference_group"].value_counts().to_dict(),
        "spearman_rating_vs_purchases": corr,
        "note": "Purchase counts are shown beside ratings but are never used as evidence of liking.",
    }


# ----------------------------------------------------------------------------- health
def health_series(ds: Dataset) -> pd.DataFrame:
    """Measurements plus BMI derived from each weight reading and the recorded height."""
    h = ds.health[["measurement_date", "indicator", "value", "unit", "source"]].copy()
    h["derived"] = False
    height_m = float(ds.users.iloc[0]["height_cm"]) / 100
    w = h[h["indicator"] == "weight"].copy()
    w["indicator"], w["unit"], w["derived"] = "bmi", "kg/m2", True
    w["value"] = (w["value"] / height_m ** 2).round(1)
    w["source"] = "derived: weight / height^2"
    return pd.concat([h, w], ignore_index=True).sort_values(["indicator", "measurement_date"])


def health_summary(ds: Dataset) -> list[dict]:
    s = health_series(ds)
    ranges = ds.ranges.set_index("indicator")
    out = []
    for ind, g in s.groupby("indicator"):
        g = g.sort_values("measurement_date")
        latest = float(g["value"].iloc[-1])
        lo = hi = None
        src = None
        if ind in ranges.index:
            r = ranges.loc[ind]
            lo = None if pd.isna(r["lower"]) or r["lower"] == "" else float(r["lower"])
            hi = None if pd.isna(r["upper"]) or r["upper"] == "" else float(r["upper"])
            src = r["source"]
        out.append({
            "indicator": ind, "unit": g["unit"].iloc[0], "measurements": int(len(g)),
            "first_date": g["measurement_date"].iloc[0].date().isoformat(), "first_value": float(g["value"].iloc[0]),
            "latest_date": g["measurement_date"].iloc[-1].date().isoformat(), "latest_value": latest,
            "change": round(latest - float(g["value"].iloc[0]), 2) if len(g) > 1 else None,
            "median_days_between": float(g["measurement_date"].diff().dt.days.median()) if len(g) > 1 else None,
            "reference_lower": lo, "reference_upper": hi, "reference_source": src,
            "latest_status": goal_status(latest, "range", lower=lo, upper=hi) if src else STATUS_INSUFFICIENT,
            "derived": bool(g["derived"].iloc[0]),
        })
    return out


def latest_weight(ds: Dataset) -> float | None:
    w = ds.health[ds.health["indicator"] == "weight"].sort_values("measurement_date")
    return float(w["value"].iloc[-1]) if len(w) else None


# ----------------------------------------------------------------------------- findings
def key_findings(ds: Dataset) -> list[dict]:
    """Findings stated as observed associations only; every number is computed from the dataset."""
    out = []
    s = spending_summary(ds)
    by_type = {r["record_type"]: r for r in s["by_record_type"]}
    delivery = by_type.get("delivery_order", {"spending_inr": 0, "transactions": 0})
    c = s["components_inr"]
    fees = c["delivery_fees"] + c["other_charges"] + c["tax"]
    out.append({
        "title": "Delivery dominates spending",
        "detail": f"Delivery orders account for Rs {delivery['spending_inr']:,.0f} of Rs {s['total_spending_inr']:,.0f} "
                  f"({delivery['spending_inr'] / s['total_spending_inr'] * 100:.0f}%) across {delivery['transactions']} "
                  f"orders. Tax, delivery and platform charges add Rs {fees:,.0f} "
                  f"({fees / s['total_spending_inr'] * 100:.1f}% of spending); discounts saved Rs {c['discounts']:,.0f}.",
        "evidence": "spending_summary(): sum of order final_total by record type",
    })
    ns = nutrition_summary(ds)
    for g in ns["goals"]:
        if g["goal_key"] in ("protein", "fiber") and g["average_logged"] is not None:
            out.append({
                "title": f"Logged {'fibre' if g['goal_key'] == 'fiber' else g['goal_key']} is {g['status'].lower()}",
                "detail": f"Average logged intake is {g['average_logged']:g} {g['unit'].split('/')[0]}/day vs a documented "
                          f"target of {g['target']:g} ({g['pct_of_target']}%), over {ns['days_logged']} logged days. "
                          "Logging is incomplete, so true intake may be higher.",
                "evidence": "nutrition_summary(): mean of daily consumed totals over logged days",
            })
    t = preference_table(ds)
    home_foods = set(ds.foods.loc[ds.foods["vendor_id"].isin(
        ds.vendors.loc[ds.vendors["channel"] == "home", "vendor_id"]), "food_id"])
    t = t[~t["food_id"].isin(home_foods)]  # home-cooked dishes are never "purchased"
    rated = t[(t["n_ratings"] >= 3)]
    purchase_rank = t["purchase_events"].rank(ascending=False, method="min")
    gap = rated[(purchase_rank.loc[rated.index] <= 10) & (rated["latest_label"].isin(["acceptable", "disliked"]))]
    if len(gap):
        top = gap.sort_values(["mean_rating", "purchase_events"], ascending=[True, False]).iloc[0]
        out.append({
            "title": "Frequent purchases are not the same as preferences",
            "detail": f"{top['food_name']} is #{int(purchase_rank[top.name])} by purchase count "
                      f"({top['purchase_events']} purchases) but has a "
                      f"mean rating of {top['mean_rating']:.1f}/5 and latest label '{top['latest_label']}'. "
                      f"Spearman correlation between rating and purchase count across rated foods: "
                      f"{preference_summary(ds)['spearman_rating_vs_purchases']}.",
            "evidence": "preference_table(): explicit feedback vs purchase events, kept as separate columns",
        })
    liked_rare = t[(t["preference_group"] == "Positive") & (t["n_ratings"] >= 3)].sort_values("purchase_events")
    if len(liked_rare):
        r = liked_rare.iloc[0]
        out.append({
            "title": "Well-rated options are under-used",
            "detail": f"{r['food_name']} is rated {r['mean_rating']:.1f}/5 ({r['n_ratings']} ratings) yet was purchased only "
                      f"{r['purchase_events']} times.",
            "evidence": "preference_table()",
        })
    hs = {h["indicator"]: h for h in health_summary(ds)}
    if "weight" in hs and hs["weight"]["change"] is not None:
        w = hs["weight"]
        out.append({
            "title": "Weight trend (association only)",
            "detail": f"Recorded weight changed by {w['change']:+.1f} kg ({w['first_value']} -> {w['latest_value']} kg, "
                      f"{w['measurements']} readings, {w['first_date']} to {w['latest_date']}). This is not attributed "
                      "to any food choice; measurement gaps exist (e.g. March).",
            "evidence": "health_summary()",
        })
    return out
