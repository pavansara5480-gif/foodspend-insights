import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response

from foodspend_core import analytics as A
from foodspend_core.constants import MEAL_SHARES, SPENDING_RECORD_TYPES
from foodspend_core.recommender import DISCLAIMER, recommend

from .params import get_choice, get_int, period
from .services import get_dataset


def clean(obj):
    """Make pandas/numpy values JSON-safe (NaN -> None, timestamps -> ISO dates)."""
    if isinstance(obj, pd.DataFrame):
        return [clean(r) for r in obj.to_dict("records")]
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.date().isoformat() if obj.hour == obj.minute == 0 else obj.isoformat(timespec="minutes")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is pd.NaT or obj is pd.NA:
        return None
    return obj


def dataset_for(request):
    start, end = period(request)
    ds = get_dataset()
    return A.filter_period(ds, start, end), start, end


def period_payload(ds, start, end):
    return {"start": (start or ds.orders["order_date"].min()).isoformat()[:10] if len(ds.orders) else None,
            "end": (end or ds.orders["order_date"].max()).isoformat()[:10] if len(ds.orders) else None,
            "orders_in_period": int(len(ds.orders))}


@api_view(["GET"])
def dashboard(request):
    ds, start, end = dataset_for(request)
    full = get_dataset()
    rec = recommend(full, "lunch", "protein")
    r = rec.get("recommended")
    return Response(clean({
        "period": period_payload(ds, start, end),
        "spending": A.spending_summary(ds),
        "monthly_spending": A.spending_by_month(ds),
        "spending_by_category": A.spending_by_category(ds),
        "top_foods": A.purchase_frequency(ds, top=8),
        "nutrition": A.nutrition_summary(ds),
        "preferences": A.preference_summary(ds),
        "health": A.health_summary(ds),
        "recommendation_preview": None if r is None else {
            "name": r["name"], "cost": r["cost"]["total"], "nutrients": r["nutrients"],
            "confidence": r["confidence"]["level"], "goal": rec["context"]["goal"]["goal_name"],
            "meal_type": "lunch", "budget": rec["context"]["budget"]},
        "synthetic_data": True,
    }))


@api_view(["GET"])
def spending(request):
    ds, start, end = dataset_for(request)
    return Response(clean({
        "period": period_payload(ds, start, end),
        "summary": A.spending_summary(ds),
        "monthly": A.spending_by_month(ds),
        "by_category": A.spending_by_category(ds),
        "by_meal_type": A.spending_by(ds, "meal_type"),
        "by_vendor": A.spending_by(ds, "vendor"),
        "by_record_type": A.spending_by(ds, "record_type"),
        "meal_source_pattern": A.meal_source_pattern(ds),
        "notes": ["Totals include discounts (subtracted), tax, delivery fees and other charges.",
                  "Category and food rows use item line totals; order-level charges are a separate row so the "
                  "breakdown sums to total spending.",
                  "Home-meal ingredient costs are estimates and are excluded from spending."],
    }))


@api_view(["GET"])
def frequency(request):
    ds, start, end = dataset_for(request)
    top = get_int(request, "top", 15, 1, 100)
    return Response(clean({"period": period_payload(ds, start, end), "foods": A.purchase_frequency(ds, top),
                           "note": "Purchase events count spending transactions containing the food. They do not "
                                   "prove consumption or liking."}))


@api_view(["GET"])
def nutrition(request):
    ds, start, end = dataset_for(request)
    freq = get_choice(request, "freq", {"W", "M"}, "M")
    daily = A.daily_intake(ds)
    return Response(clean({"period": period_payload(ds, start, end), "summary": A.nutrition_summary(ds),
                           "trend": A.nutrition_trend(ds, freq), "freq": freq,
                           "daily": daily.assign(order_date=daily["order_date"].dt.date.astype(str))
                           if len(daily) else [],
                           "meal_shares": MEAL_SHARES}))


@api_view(["GET"])
def findings(request):
    ds = get_dataset()
    return Response(clean({"findings": A.key_findings(ds), "disclaimer": DISCLAIMER}))


@api_view(["GET"])
def data_quality(request):
    ds = get_dataset()

    def read(name):
        p = settings.REPORTS_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    o, it = ds.orders, ds.items
    recon = it.groupby("order_id")["line_total_inr"].sum().round(2)
    sub = o.set_index("order_id")["items_subtotal_inr"]
    diff = (recon.reindex(sub.index) - sub).abs()
    so = A.spending_orders(ds)
    joined = it.merge(so[["order_id", "final_total_inr"]], on="order_id")
    naive = float(joined["final_total_inr"].sum())
    correct = float(so["final_total_inr"].sum())
    live = {
        "database": connection.vendor,
        "row_counts": {"orders": len(o), "order_items": len(it), "foods": len(ds.foods), "feedback": len(ds.feedback),
                       "health_measurements": len(ds.health), "meal_options": len(ds.meal_options)},
        "orders_where_item_lines_differ_from_subtotal": int((diff > 0.01).sum()),
        "orders_without_items": int(diff.isna().sum()),
        "join_duplication_check": {
            "correct_order_level_total": round(correct, 2),
            "naive_item_join_total": round(naive, 2),
            "explanation": "Summing order totals after joining to items would overstate spending by "
                           f"Rs {naive - correct:,.2f}; all spending metrics aggregate at order level instead."},
        "nutrition_unknown_values": {c: int(ds.nutrition[c].isna().sum())
                                     for c in ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]},
        "consumption_status": it["consumption_status"].value_counts().to_dict(),
        "coverage": {"first_date": o["order_date"].min(), "last_date": o["order_date"].max(),
                     "days_with_records": int(o["order_date"].nunique())},
    }
    return Response(clean({
        "cleaning_report": read("data_quality_report.json"),
        "import_report": read("import_report.json"),
        "live_checks": live,
        "disclosures": [
            "All records are SYNTHETIC, generated by analysis/scripts/generate_synthetic_data.py (seed 20251027) "
            "for a fictional person. They are not real customer or patient data.",
            "Nutrient values are synthetic estimates approximating typical published values (IFCT 2017 / USDA "
            "FoodData Central); they were not verified item by item.",
            "Prices are the latest values in the synthetic history, not current market prices.",
            "Grocery purchases have unknown consumption. Nutrition intake is computed only from logged meals "
            "(portion consumed recorded); purchases are not assumed to be eaten.",
            "Health indicators are simulated; no causal link between food and health changes is claimed.",
            f"Spending counts {sorted(SPENDING_RECORD_TYPES)}; home-meal ingredient costs are estimates and excluded.",
        ],
        "assumptions": [
            "Nutrients scale linearly: amount / basis quantity x value per basis.",
            "Meal shares of daily targets: " + ", ".join(f"{k} {int(v * 100)}%" for k, v in MEAL_SHARES.items()) + ".",
            "Missing meal types on food orders were inferred from order time and flagged.",
            "A recommendation's delivery fee is the vendor's median recent delivery + platform charges.",
        ],
    }))
