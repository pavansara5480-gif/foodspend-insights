"""Build docs/FoodSpend_Insights.pptx.

1. Computes every number shown in the deck with foodspend_core on data/processed/*.csv
   (the same code the API and notebooks use) and writes docs/presentation/deck_data.json.
2. Runs docs/presentation/build_deck.js (pptxgenjs) to lay out the slides with native charts.

Usage (project root, venv active):  python docs/build_presentation.py
Requires Node.js and `npm install` in docs/presentation once.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from foodspend_core import analytics as A  # noqa: E402
from foodspend_core.recommender import budget_comparison, recommend, simulate  # noqa: E402

ds = A.load_processed(ROOT / "data" / "processed")
quality = json.loads((ROOT / "analysis" / "reports" / "data_quality_report.json").read_text(encoding="utf-8"))
s = A.spending_summary(ds)
ns = A.nutrition_summary(ds)
pt = A.preference_table(ds)
ps = A.preference_summary(ds)
health = A.health_summary(ds)


def meal(e):
    return {"name": e["name"], "cost": e["cost"]["total"], "protein": e["nutrients"]["protein_g"],
            "fiber": e["nutrients"]["fiber_g"], "kcal": e["nutrients"]["calories_kcal"],
            "score": e["scores"]["total"], "items": [i["food_name"] for i in e["items"]]}


rec_any = recommend(ds, "lunch", "protein", 350)
rec_del = recommend(ds, "lunch", "protein", 350, source="delivery")
base = [{"food_id": "F004", "servings": 1}]
scenarios = {
    "Serving x2": [{"op": "set_servings", "food_id": "F004", "servings": 2}],
    "Add boiled eggs": [{"op": "add", "food_id": "F023", "servings": 1}],
    "Swap: chicken salad bowl": [{"op": "substitute", "food_id": "F004", "with_food_id": "F008"}],
    "Swap: home thali + curd": [{"op": "substitute", "food_id": "F004", "with_food_id": "F027"},
                                {"op": "add", "food_id": "F021"}],
}
sim = []
for name, ops in scenarios.items():
    r = simulate(ds, base, ops, meal_type="lunch", goal_key="protein", budget=350)
    sim.append({"name": name, "cost_diff": r["differences"]["cost"], "protein_diff": r["differences"]["nutrients"]["protein_g"],
                "kcal_diff": r["differences"]["nutrients"]["calories_kcal"], "modified_cost": r["modified"]["cost"]["total"],
                "within_budget": r["verdict"]["modified_within_budget"]})
budgets = []
for b in [150, 250, 350, 500]:
    bc = budget_comparison(ds, b, "lunch", "protein", source="delivery")
    o = bc["options"][0] if bc["options"] else None
    budgets.append({"budget": b, "feasible": bc["feasible_count"], "top": o and o["name"], "cost": o and o["cost"]["total"],
                    "remaining": o and o["budget"]["remaining"], "util": o and o["budget"]["utilization_pct"],
                    "protein": o and o["nutrients"]["protein_g"]})

monthly = A.spending_by_month(ds)
rated = pt[pt["n_ratings"] > 0]
data = {
    "period": [s["period_start"], s["period_end"]],
    "spending": {"total": s["total_spending_inr"], "transactions": s["transactions"], "food_orders": s["food_orders"],
                 "avg_food_order": s["average_food_order_value_inr"], "avg_month": s["average_monthly_spending_inr"],
                 "components": s["components_inr"],
                 "by_type": {r["record_type"]: r["spending_inr"] for r in s["by_record_type"]},
                 "home_meals": s["home_meals_logged"]},
    "monthly": {"labels": monthly["month"].tolist(),
                "delivery": monthly["delivery_order"].round(0).tolist(),
                "cafe": monthly["cafe_purchase"].round(0).tolist(),
                "grocery": monthly["grocery_purchase"].round(0).tolist()},
    "nutrition": {"days_logged": ns["days_logged"], "coverage": ns["logging_coverage_pct"], "avg": ns["average_daily_logged"],
                  "goals": [{k: g[k] for k in ("goal_key", "nutrient", "average_logged", "target", "pct_of_target", "status", "unit")}
                            for g in ns["goals"]],
                  "energy": [{k: e[k] for k in ("indicator", "value", "status")} for e in ns["energy_distribution"]],
                  "unknown_fiber_items": ns["completeness"]["meal_items_unknown_fiber"]},
    "preferences": {"records": ps["feedback_records"], "rated": ps["foods_rated"], "avg": ps["average_rating"],
                    "spearman": ps["spearman_rating_vs_purchases"], "groups": ps["groups"],
                    "points": [{"name": r.food_name, "x": int(r.purchase_events), "y": float(r.mean_rating)} for r in rated.itertuples()]},
    "health": [{k: h[k] for k in ("indicator", "unit", "first_value", "latest_value", "change", "measurements",
                                  "reference_lower", "reference_upper", "latest_status")} for h in health],
    "quality": {"raw": {k: v["raw_rows"] for k, v in quality["tables"].items()},
                "clean": {k: v["clean_rows"] for k, v in quality["tables"].items()},
                "rejected": quality["rejected_total"], "checks": quality["checks"], "coverage": quality["coverage"]},
    "rec_any": {"context": {"meal_target": rec_any["context"]["meal_target"], "kcal_allowance": rec_any["context"]["kcal_allowance"],
                            "daily_target": rec_any["context"]["goal"]["daily_target"],
                            "recent": rec_any["context"]["recent_intake"]["goal_status_recent"]["average_logged"]},
                "best": meal(rec_any["recommended"]) | {"confidence": rec_any["recommended"]["confidence"]["level"],
                                                         "reasons": rec_any["recommended"]["reasons"]},
                "alternatives": [meal(a) | {"type": a["title"]} for a in rec_any["alternatives"]],
                "excluded": [f"{e['food_name']} ({e['latest_label']})" for e in rec_any["excluded_by_feedback"]],
                "evaluated": rec_any["candidates_evaluated"], "feasible": rec_any["feasible_candidates"]},
    "rec_delivery": {"best": meal(rec_del["recommended"]), "alternatives": [meal(a) | {"type": a["title"]} for a in rec_del["alternatives"]]},
    "scenarios": sim,
    "budgets": budgets,
    "findings": A.key_findings(ds),
}
out = ROOT / "docs" / "presentation" / "deck_data.json"
out.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
print("wrote", out)
subprocess.run(["node", str(ROOT / "docs" / "presentation" / "build_deck.js")], check=True, cwd=ROOT / "docs" / "presentation")
