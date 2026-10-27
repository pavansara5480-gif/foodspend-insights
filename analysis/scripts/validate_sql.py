"""Run analysis/sql/analysis_queries.sql against the configured database (backend/.env) and compare each
result with the pandas implementation in foodspend_core applied to data/processed/*.csv.

Usage (from the project root, with the venv active):
    python analysis/scripts/validate_sql.py
Writes analysis/reports/sql_validation.md and exits non-zero if any comparison fails.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from foodspend_core import analytics as A  # noqa: E402


def load_queries() -> dict[str, str]:
    text = (ROOT / "analysis" / "sql" / "analysis_queries.sql").read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def run(sql: str) -> list[tuple]:
    with connection.cursor() as c:
        c.execute(sql)
        return c.fetchall()


def main() -> int:
    q = load_queries()
    ds = A.load_processed(ROOT / "data" / "processed")
    s = A.spending_summary(ds)
    ns = A.nutrition_summary(ds)
    cats = A.spending_by_category(ds).set_index("label")["spending_inr"]
    top = A.purchase_frequency(ds, top=10)
    pref = A.preference_table(ds)
    checks = []

    def check(name, sql_value, pandas_value, tol=0.05):
        ok = abs(float(sql_value) - float(pandas_value)) <= tol
        checks.append((name, sql_value, pandas_value, ok))

    total, n = run(q["total_spending"])[0]
    check("total spending (INR)", total, s["total_spending_inr"])
    check("transactions", n, s["transactions"], 0)
    comp = run(q["spending_components"])[0]
    for name, v in zip(["items_subtotal", "discounts", "tax", "delivery_fees", "other_charges"], comp):
        check(f"component: {name}", v, s["components_inr"][name])
    months = run(q["monthly_spending"])
    pm = A.spending_by_month(ds).set_index("month")["total"]
    check("monthly spending: months", len(months), len(pm), 0)
    check("monthly spending: max abs diff", max(abs(float(v) - pm[m]) for m, v, _ in months), 0, 0.05)
    for label, v in run(q["spending_by_category"]):
        check(f"category: {label}", v, cats[label])
    naive = run(q["naive_join_duplication"])[0][0]
    checks.append(("naive join overstates spending (expected)", naive, total, float(naive) > float(total)))
    for (name, events, _), (_, row) in zip(run(q["top_purchased_foods"]), top.iterrows()):
        check(f"top food events: {name}", events, top.set_index("food_name").loc[name, "purchase_events"], 0)
    kcal, protein, days = run(q["average_daily_logged_intake"])[0]
    check("avg daily logged kcal", kcal, ns["average_daily_logged"]["calories_kcal"], 0.1)
    check("avg daily logged protein", protein, ns["average_daily_logged"]["protein_g"], 0.1)
    check("days logged", days, ns["days_logged"], 0)
    check("meal items with unknown fibre", run(q["unknown_fiber_items"])[0][0],
          ns["completeness"]["meal_items_unknown_fiber"], 0)
    pidx = pref.set_index("food_name")
    for name, nr, mean in run(q["preference_by_food"])[:10]:
        check(f"mean rating: {name}", mean, pidx.loc[name, "mean_rating"], 0.01)

    failed = [c for c in checks if not c[3]]
    lines = ["# SQL vs pandas validation", "",
             f"Database: `{connection.vendor}` · queries: `analysis/sql/analysis_queries.sql` · "
             "pandas: `foodspend_core` on `data/processed/*.csv`", "",
             "| Check | SQL | pandas | Result |", "|---|---:|---:|---|"]
    lines += [f"| {n} | {a} | {b} | {'PASS' if ok else 'FAIL'} |" for n, a, b, ok in checks]
    lines += ["", f"**{len(checks) - len(failed)} / {len(checks)} checks passed.**"]
    out = ROOT / "analysis" / "reports" / "sql_validation.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-1:]))
    for c in failed:
        print("FAIL:", c)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
