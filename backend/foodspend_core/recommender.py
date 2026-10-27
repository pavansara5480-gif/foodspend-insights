"""Transparent rule-based next-meal recommendation, scenario (what-if) and budget analysis.

Ranking method (documented in docs/DECISIONS.md and returned by the API as `method`):

  meal_target      = daily goal target x meal share (breakfast 25%, lunch 35%, snack 10%, dinner 30%)
  kcal_allowance   = daily energy reference (2,110 kcal) x meal share
  goal_progress    = at_least goals: min(goal nutrient / meal_target, 1)      (overshoot earns nothing extra)
                     at_most goal (calories): calorie_fit
  calorie_fit      = 1 if 0.6A <= kcal <= A;  kcal / 0.6A below that;  max(0, 1 - (kcal - A) / A) above A
  goal_score       = 0.7 x goal_progress + 0.3 x secondary
                     (secondary = calorie_fit for nutrient goals, protein progress for the calorie goal)
  preference_score = (adjusted rating - 1) / 4 per food, 0.5 when the food has no feedback;
                     adjusted = (n x mean + 2 x overall mean rating) / (n + 2)  (shrinkage);
                     combined as 0.75 x main + 0.25 x add-on
  cost_score       = 1 - cost / budget
  total            = w_goal x goal_score + w_pref x preference_score + w_cost x cost_score
                     (default weights 0.5 / 0.3 / 0.2)
  Hard constraints : cost <= budget; food listed for the meal type; latest explicit label not in
                     {disliked, avoid}.
  Tie-break        : higher total, then higher preference, then lower cost, then name.

Candidates: every main option for the meal type at each allowed serving, alone or with one add-on
(a side from the same vendor, or a pantry food that appears in the purchase history).
Cost: items subtotal + tax (vendor rate) + estimated delivery/platform fees per delivery vendor.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .analytics import Dataset, filter_period, latest_weight, nutrition_summary, preference_table
from .constants import (DEFAULT_DAILY_KCAL, DEFAULT_WEIGHTS, EXCLUDED_LABELS, MEAL_SHARES, NUTRIENTS,
                        SERVING_UNCERTAINTY)
from .formulas import budget_metrics, goal_status, nutrient_amounts, pct

MIN_SERVINGS, MAX_SERVINGS = 0.25, 5.0
RATING_PRIOR_WEIGHT = 2  # pseudo-ratings at the person's overall mean added to each food's ratings
SOURCES = {"any": None, "delivery": {"delivery"}, "home": {"home"}}
DEFAULT_BUDGET = 350.0


class ScenarioError(ValueError):
    pass


# ----------------------------------------------------------------------------- catalogue
@dataclass
class Food:
    food_id: str
    name: str
    category: str
    role: str
    vendor_id: str
    channel: str
    serving_size: float
    unit: str
    price_per_serving: float
    price_source: str
    price_date: str
    allowed_servings: list[float]
    meal_types: set[str]
    per_serving: dict  # nutrient -> value or None


@dataclass
class Context:
    ds: Dataset
    foods: dict[str, Food]
    vendors: dict[str, dict]
    prefs: dict[str, dict]
    goal: dict
    meal_type: str
    budget: float
    weights: dict
    meal_share: float
    daily_kcal: float
    reference_date: pd.Timestamp
    recent: dict = field(default_factory=dict)
    source: str = "any"

    @property
    def meal_target(self) -> float:
        return self.goal["daily_target"] * self.meal_share

    @property
    def kcal_allowance(self) -> float:
        return self.daily_kcal * self.meal_share


def build_catalog(ds: Dataset) -> dict[str, Food]:
    nut = ds.nutrition.set_index("food_id")
    vend = ds.vendors.set_index("vendor_id")
    opts = ds.meal_options
    out = {}
    for f in ds.foods.to_dict("records"):
        fo = opts[opts["food_id"] == f["food_id"]]
        if fo.empty or f["food_id"] not in nut.index:
            continue
        first = fo.iloc[0]
        n = nut.loc[f["food_id"]]
        values = {k: (None if pd.isna(n[k]) else float(n[k])) for k in NUTRIENTS}
        per_serving = nutrient_amounts(float(first["serving_size"]), first["serving_unit"],
                                       float(n["basis_quantity"]), n["basis_unit"], values)
        out[f["food_id"]] = Food(
            food_id=f["food_id"], name=f["food_name"], category=f["category"], role=f["role"],
            vendor_id=f["vendor_id"], channel=vend.loc[f["vendor_id"], "channel"],
            serving_size=float(first["serving_size"]), unit=first["serving_unit"],
            price_per_serving=float(first["price_per_serving_inr"]), price_source=first["price_source"],
            price_date=str(first["price_date"])[:10],
            allowed_servings=[float(x) for x in str(first["allowed_servings"]).split(",")],
            meal_types=set(fo["meal_type"]), per_serving=per_serving)
    return out


def vendor_costs(ds: Dataset) -> dict[str, dict]:
    """Tax rate and an estimated per-order fee (median delivery + other charges, last 90 days of history)."""
    o = ds.orders[ds.orders["record_type"] == "delivery_order"]
    recent = o[o["order_date"] >= o["order_date"].max() - pd.Timedelta(days=90)] if len(o) else o
    out = {}
    for v in ds.vendors.to_dict("records"):
        vo = recent[recent["vendor_id"] == v["vendor_id"]]
        if v["channel"] == "delivery" and len(vo):
            fee = float((vo["delivery_fee_inr"] + vo["other_charges_inr"]).median())
            basis = f"median delivery + platform/packaging charges of {len(vo)} orders in the last 90 days of history"
        elif v["channel"] == "delivery":
            fee = float(v["typical_delivery_fee_inr"])
            basis = "vendor typical delivery fee (no recent orders)"
        else:
            fee, basis = 0.0, "no delivery fee"
        tax = float(v["tax_rate"]) if v["channel"] in ("delivery", "cafe") else 0.0
        out[v["vendor_id"]] = {"vendor_name": v["vendor_name"], "channel": v["channel"], "tax_rate": tax,
                               "fee_estimate": round(fee, 2), "fee_basis": basis}
    return out


def preference_lookup(ds: Dataset) -> dict[str, dict]:
    """Per-food explicit feedback. The rating used for scoring is shrunk toward the person's overall mean:
    adjusted = (n x mean + K x overall_mean) / (n + K), so one rating cannot dominate the ranking."""
    t = preference_table(ds)
    prior = float(ds.feedback["rating"].mean()) if len(ds.feedback) else 3.0
    out = {}
    for r in t.to_dict("records"):
        n = int(r["n_ratings"])
        mean = None if pd.isna(r["mean_rating"]) else float(r["mean_rating"])
        out[r["food_id"]] = {
            "n_ratings": n,
            "mean_rating": mean,
            "adjusted_rating": None if mean is None else round((n * mean + RATING_PRIOR_WEIGHT * prior)
                                                               / (n + RATING_PRIOR_WEIGHT), 2),
            "latest_label": None if pd.isna(r["latest_label"]) else r["latest_label"],
            "latest_feedback_date": r["latest_feedback_date"],
            "purchase_events": int(r["purchase_events"]),
            "logged_eaten_events": int(r["logged_eaten_events"]),
        }
    return out


def goal_definition(ds: Dataset, goal_key: str, target_override: float | None = None) -> dict:
    g = ds.goals[ds.goals["goal_key"] == goal_key]
    if g.empty:
        raise ScenarioError(f"unknown goal '{goal_key}'. Available: {sorted(ds.goals['goal_key'])}")
    g = g.iloc[0]
    target = float(g["target_value"]) if target_override is None else float(target_override)
    return {"goal_key": goal_key, "goal_name": g["goal_name"], "nutrient": g["nutrient"],
            "direction": g["direction"], "daily_target": target, "unit": g["unit"],
            "documented_target": float(g["target_value"]), "target_overridden": target_override is not None,
            "reference_source": g["reference_source"]}


def make_context(ds: Dataset, meal_type: str, goal_key: str, budget: float, weights: dict | None = None,
                 target_override: float | None = None, source: str = "any") -> Context:
    if source not in SOURCES:
        raise ScenarioError(f"source must be one of {list(SOURCES)}")
    if meal_type not in MEAL_SHARES:
        raise ScenarioError(f"meal_type must be one of {list(MEAL_SHARES)}")
    if budget is None or budget < 0:
        raise ScenarioError("budget must be a non-negative number")
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if k in w and v is not None:
                if v < 0:
                    raise ScenarioError("weights must be non-negative")
                w[k] = float(v)
    s = sum(w.values())
    if s <= 0:
        raise ScenarioError("at least one weight must be positive")
    w = {k: round(v / s, 4) for k, v in w.items()}
    ref = ds.orders["order_date"].max()
    goal = goal_definition(ds, goal_key, target_override)
    recent_ds = filter_period(ds, ref - pd.Timedelta(days=29), ref)
    rs = nutrition_summary(recent_ds)
    goal_row = next((r for r in rs["goals"] if r["goal_key"] == goal_key), None)
    kcal_goal = ds.goals[ds.goals["goal_key"] == "calories"]
    daily_kcal = float(kcal_goal["target_value"].iloc[0]) if len(kcal_goal) else DEFAULT_DAILY_KCAL
    if goal_key == "calories":
        daily_kcal = goal["daily_target"]
    recent = {"window": f"{(ref - pd.Timedelta(days=29)).date()} to {ref.date()}",
              "days_logged": rs["days_logged"], "logging_coverage_pct": rs["logging_coverage_pct"],
              "average_daily_logged": rs["average_daily_logged"],
              "goal_status_recent": None if goal_row is None else {
                  **goal_row, "target": goal["daily_target"],
                  "pct_of_target": pct(goal_row["average_logged"], goal["daily_target"])}}
    if goal_row is not None and target_override is not None:
        recent["goal_status_recent"]["status"] = goal_status(goal_row["average_logged"], goal["direction"],
                                                             target=goal["daily_target"])
    return Context(ds=ds, foods=build_catalog(ds), vendors=vendor_costs(ds), prefs=preference_lookup(ds),
                   goal=goal, meal_type=meal_type, budget=float(budget), weights=w,
                   meal_share=MEAL_SHARES[meal_type], daily_kcal=daily_kcal, reference_date=ref, recent=recent,
                   source=source)


# ----------------------------------------------------------------------------- evaluation
def meal_cost(lines: list[tuple[str, float]], ctx: Context) -> dict:
    by_vendor: dict[str, float] = {}
    for fid, s in lines:
        f = ctx.foods[fid]
        by_vendor[f.vendor_id] = by_vendor.get(f.vendor_id, 0.0) + f.price_per_serving * s
    subtotal = tax = fees = 0.0
    parts = []
    for vid, sub in by_vendor.items():
        v = ctx.vendors[vid]
        t = round(sub * v["tax_rate"], 2)
        fee = v["fee_estimate"] if v["channel"] == "delivery" else 0.0
        subtotal += sub
        tax += t
        fees += fee
        parts.append({"vendor_id": vid, "vendor_name": v["vendor_name"], "channel": v["channel"],
                      "items_subtotal": round(sub, 2), "tax": t, "fees": round(fee, 2),
                      "fee_basis": v["fee_basis"], "total": round(sub + t + fee, 2)})
    return {"items_subtotal": round(subtotal, 2), "tax": round(tax, 2), "fees": round(fees, 2),
            "total": round(subtotal + tax + fees, 2), "by_vendor": parts}


def meal_nutrients(lines: list[tuple[str, float]], ctx: Context) -> tuple[dict, dict]:
    totals = {n: 0.0 for n in NUTRIENTS}
    missing: dict[str, list[str]] = {}
    for fid, s in lines:
        f = ctx.foods[fid]
        for n in NUTRIENTS:
            v = f.per_serving[n]
            if v is None:
                missing.setdefault(n, []).append(f.name)
            else:
                totals[n] += v * s
    return {n: round(v, 1) for n, v in totals.items()}, missing


def calorie_fit(kcal: float, allowance: float) -> float:
    if allowance <= 0:
        return 0.0
    lo = 0.6 * allowance
    if kcal < lo:
        return round(kcal / lo, 4)
    if kcal <= allowance:
        return 1.0
    return round(max(0.0, 1 - (kcal - allowance) / allowance), 4)


def evaluate(lines: list[tuple[str, float]], ctx: Context) -> dict:
    nutrients, missing = meal_nutrients(lines, ctx)
    cost = meal_cost(lines, ctx)
    goal_n = ctx.goal["nutrient"]
    fit = calorie_fit(nutrients["calories_kcal"], ctx.kcal_allowance)
    if ctx.goal["direction"] == "at_least":
        progress = min(nutrients[goal_n] / ctx.meal_target, 1.0) if ctx.meal_target > 0 else 0.0
        secondary = fit
    else:
        progress = fit
        prot = ctx.ds.goals[ctx.ds.goals["goal_key"] == "protein"]
        prot_target = float(prot["target_value"].iloc[0]) * ctx.meal_share if len(prot) else None
        secondary = min(nutrients["protein_g"] / prot_target, 1.0) if prot_target else 0.0
    goal_score = 0.7 * progress + 0.3 * secondary

    pref_parts = []
    for i, (fid, _) in enumerate(lines):
        p = ctx.prefs.get(fid, {})
        score = 0.5 if not p.get("adjusted_rating") else (p["adjusted_rating"] - 1) / 4
        pref_parts.append((0.75 if i == 0 else 0.25 / max(1, len(lines) - 1), score))
    wsum = sum(w for w, _ in pref_parts) or 1
    pref_score = sum(w * s for w, s in pref_parts) / wsum

    cost_score = max(0.0, 1 - cost["total"] / ctx.budget) if ctx.budget > 0 else 0.0
    total = (ctx.weights["goal"] * goal_score + ctx.weights["preference"] * pref_score
             + ctx.weights["cost"] * cost_score)
    goal_amount = nutrients[goal_n]
    return {
        "items": [item_detail(fid, s, ctx) for fid, s in lines],
        "name": " + ".join(f"{ctx.foods[fid].name}{'' if s == 1 else f' x{s:g}'}" for fid, s in lines),
        "nutrients": nutrients,
        "nutrients_missing": missing,
        "nutrient_range": {n: [round(v * (1 - SERVING_UNCERTAINTY), 1), round(v * (1 + SERVING_UNCERTAINTY), 1)]
                           for n, v in nutrients.items()},
        "cost": cost,
        "budget": budget_metrics(cost["total"], ctx.budget),
        "goal_contribution": {
            "nutrient": goal_n, "amount": goal_amount, "meal_target": round(ctx.meal_target, 1),
            "pct_of_meal_target": pct(goal_amount, ctx.meal_target),
            "pct_of_daily_target": pct(goal_amount, ctx.goal["daily_target"]),
            "lower_bound_only": goal_n in missing,
        },
        "calories_vs_allowance": {"kcal": nutrients["calories_kcal"], "allowance": round(ctx.kcal_allowance),
                                  "pct": pct(nutrients["calories_kcal"], ctx.kcal_allowance)},
        "scores": {"goal_progress": round(progress, 4), "secondary": round(secondary, 4),
                   "goal": round(goal_score, 4), "preference": round(pref_score, 4),
                   "cost": round(cost_score, 4), "total": round(total, 4)},
    }


def item_detail(fid: str, servings: float, ctx: Context) -> dict:
    f = ctx.foods[fid]
    p = ctx.prefs.get(fid, {})
    return {
        "food_id": fid, "food_name": f.name, "category": f.category, "role": f.role,
        "vendor": ctx.vendors[f.vendor_id]["vendor_name"], "channel": f.channel,
        "servings": servings, "amount": round(f.serving_size * servings, 1), "unit": f.unit,
        "price_per_serving": f.price_per_serving, "price_source": f.price_source, "price_date": f.price_date,
        "nutrients": {n: None if v is None else round(v * servings, 1) for n, v in f.per_serving.items()},
        "preference": {
            "mean_rating": p.get("mean_rating"), "adjusted_rating": p.get("adjusted_rating"),
            "n_ratings": p.get("n_ratings", 0),
            "latest_label": p.get("latest_label"), "latest_feedback_date": p.get("latest_feedback_date"),
            "purchase_events": p.get("purchase_events", 0), "logged_eaten_events": p.get("logged_eaten_events", 0),
        },
    }


def confidence(ev: dict, ctx: Context) -> dict:
    score, factors = 1.0, []
    if ev["nutrients_missing"]:
        score -= 0.25
        factors.append("Unknown nutrient values: " + "; ".join(f"{n} for {', '.join(v)}"
                                                               for n, v in ev["nutrients_missing"].items()))
    main = ev["items"][0]["preference"]
    if main["n_ratings"] == 0:
        score -= 0.15
        factors.append("Main dish has no explicit feedback (preference treated as neutral)")
    elif main["n_ratings"] < 3:
        score -= 0.1
        factors.append(f"Only {main['n_ratings']} rating(s) for the main dish")
    for it in ev["items"][1:]:
        if it["preference"]["n_ratings"] == 0:
            score -= 0.05
            factors.append(f"No feedback for add-on {it['food_name']}")
    oldest = min(pd.Timestamp(it["price_date"]) for it in ev["items"])
    if (ctx.reference_date - oldest).days > 30:
        score -= 0.1
        factors.append("Price data older than 30 days")
    score -= 0.1
    factors.append("Nutrient values are synthetic estimates (+/-15% serving-size uncertainty shown)")
    cov = ctx.recent.get("logging_coverage_pct") or 0
    if cov < 70:
        score -= 0.1
        factors.append(f"Recent logging coverage is {cov}% of days")
    score = round(max(score, 0.0), 2)
    return {"score": score, "level": "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low",
            "factors": factors}


# ----------------------------------------------------------------------------- candidates
def exclusions(ctx: Context) -> list[dict]:
    out = []
    for fid, p in ctx.prefs.items():
        if p.get("latest_label") in EXCLUDED_LABELS and fid in ctx.foods:
            out.append({"food_id": fid, "food_name": ctx.foods[fid].name, "latest_label": p["latest_label"],
                        "mean_rating": p["mean_rating"], "n_ratings": p["n_ratings"],
                        "latest_feedback_date": p["latest_feedback_date"]})
    return out


def candidate_lines(ctx: Context, allowed_food_ids: set[str] | None = None) -> list[list[tuple[str, float]]]:
    excluded = {e["food_id"] for e in exclusions(ctx)}
    ok = lambda f: (ctx.meal_type in f.meal_types and f.food_id not in excluded  # noqa: E731
                    and (allowed_food_ids is None or f.food_id in allowed_food_ids))
    channels = SOURCES[ctx.source]
    mains = [f for f in ctx.foods.values() if f.role == "main" and ok(f)
             and (channels is None or f.channel in channels)]
    pantry = [f for f in ctx.foods.values() if f.role == "pantry" and ok(f)
              and ctx.prefs.get(f.food_id, {}).get("purchase_events", 0) > 0]
    sides = [f for f in ctx.foods.values() if f.role == "side" and ok(f)]
    out = []
    for m in mains:
        for s in m.allowed_servings:
            base = [(m.food_id, s)]
            out.append(base)
            addons = pantry + [sd for sd in sides if sd.vendor_id == m.vendor_id]
            for a in addons:
                out.append(base + [(a.food_id, 1.0)])
    return out


def rank(ctx: Context, allowed_food_ids: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Return (feasible ranked candidates, infeasible candidates over budget)."""
    feasible, over = [], []
    for lines in candidate_lines(ctx, allowed_food_ids):
        ev = evaluate(lines, ctx)
        ev["lines"] = lines
        (feasible if ev["cost"]["total"] <= ctx.budget else over).append(ev)
    key = lambda e: (-e["scores"]["total"], -e["scores"]["preference"], e["cost"]["total"], e["name"])  # noqa: E731
    feasible.sort(key=key)
    over.sort(key=lambda e: e["cost"]["total"])
    return feasible, over


def reasons(ev: dict, ctx: Context) -> list[str]:
    g = ev["goal_contribution"]
    unit = "kcal" if g["nutrient"] == "calories_kcal" else "g"
    label = ctx.goal["goal_name"]
    out = []
    if ctx.goal["direction"] == "at_least":
        out.append(f"Supplies {g['amount']:g} {unit} {g['nutrient'].split('_')[0]}"
                   f"{' (lower bound: some values unknown)' if g['lower_bound_only'] else ''}, "
                   f"{g['pct_of_meal_target']}% of the {ctx.meal_type} share ({g['meal_target']:g} {unit} = "
                   f"{int(ctx.meal_share * 100)}% of {ctx.goal['daily_target']:g} {unit}/day) for the goal '{label}'.")
    c = ev["calories_vs_allowance"]
    out.append(f"{c['kcal']:g} kcal against a {ctx.meal_type} allowance of {c['allowance']} kcal "
               f"({c['pct']}%; calorie-fit score {ev['scores']['secondary' if ctx.goal['direction'] == 'at_least' else 'goal_progress']:.2f}).")
    b = ev["budget"]
    out.append(f"Estimated cost Rs {b['cost']:g} (incl. tax/fees Rs {ev['cost']['tax'] + ev['cost']['fees']:g}), "
               f"leaving Rs {b['remaining']:g} of the Rs {b['budget']:g} budget ({b['utilization_pct']}% used).")
    for it in ev["items"]:
        p = it["preference"]
        if p["n_ratings"]:
            out.append(f"{it['food_name']}: mean rating {p['mean_rating']:.1f}/5 from {p['n_ratings']} feedback "
                       f"record(s) (adjusted {p['adjusted_rating']:.2f} after shrinkage), latest label "
                       f"'{p['latest_label']}' ({p['latest_feedback_date']}).")
        else:
            out.append(f"{it['food_name']}: no explicit feedback; treated as neutral "
                       f"({p['purchase_events']} past purchases are not used as evidence of liking).")
    rs = ctx.recent.get("goal_status_recent")
    if rs and rs.get("average_logged") is not None:
        out.append(f"Context: logged average {rs['average_logged']:g} {unit}/day over {ctx.recent['window']} "
                   f"({rs['pct_of_target']}% of target; status '{rs['status']}', based on {ctx.recent['days_logged']} logged days).")
    return out


def tradeoff(alt: dict, best: dict, ctx: Context) -> dict:
    n = ctx.goal["nutrient"]
    return {
        "cost_difference": round(alt["cost"]["total"] - best["cost"]["total"], 2),
        "goal_nutrient_difference": round(alt["nutrients"][n] - best["nutrients"][n], 1),
        "calorie_difference": round(alt["nutrients"]["calories_kcal"] - best["nutrients"]["calories_kcal"], 1),
        "preference_score_difference": round(alt["scores"]["preference"] - best["scores"]["preference"], 3),
        "total_score_difference": round(alt["scores"]["total"] - best["scores"]["total"], 3),
    }


def _strip(ev: dict) -> dict:
    return {k: v for k, v in ev.items() if k != "lines"} | {
        "lines": [{"food_id": f, "servings": s} for f, s in ev["lines"]]}


def recommend(ds: Dataset, meal_type: str = "lunch", goal_key: str = "protein", budget: float = DEFAULT_BUDGET,
              weights: dict | None = None, target_override: float | None = None, top_n: int = 10,
              source: str = "any") -> dict:
    ctx = make_context(ds, meal_type, goal_key, budget, weights, target_override, source)
    feasible, over = rank(ctx)
    excluded = exclusions(ctx)
    base = {"context": context_payload(ctx), "excluded_by_feedback": excluded,
            "candidates_evaluated": len(feasible) + len(over), "feasible_candidates": len(feasible),
            "over_budget_candidates": len(over), "method": METHOD, "disclaimer": DISCLAIMER}
    if not feasible:
        cheapest = over[0]["cost"]["total"] if over else None
        return base | {"recommended": None, "alternatives": [], "ranking": [],
                       "message": (f"No option in the dataset fits a budget of Rs {budget:g}. "
                                   f"The cheapest candidate costs Rs {cheapest:g}." if cheapest is not None
                                   else "No meal options are available for this meal type.")}
    best = feasible[0]
    best_main = best["lines"][0][0]
    alts = []

    def add_alt(kind: str, title: str, ev: dict | None, why: str) -> None:
        if ev is None or any(a["name"] == ev["name"] for a in alts) or ev["name"] == best["name"]:
            return
        alts.append(_strip(ev) | {"alternative_type": kind, "title": title, "why": why,
                                  "tradeoff": tradeoff(ev, best, ctx), "confidence": confidence(ev, ctx)})

    sub = next((e for e in feasible if e["lines"][0][0] != best_main), None)
    add_alt("substitution", "Substitute the main dish", sub,
            "Highest-scoring option with a different main dish.")
    bigger = next((e for e in feasible if e["lines"][0][0] == best_main
                   and e["lines"][0][1] > best["lines"][0][1]), None)
    if bigger is None:
        bigger = next((e for e in feasible if e["lines"][0][1] > 1), None)
    add_alt("serving_increase", "Increase the serving", bigger,
            "Larger allowed serving of a main dish, within budget.")
    addon = next((e for e in feasible if e["lines"][0] == best["lines"][0] and len(e["lines"]) > 1
                  and ctx.foods[e["lines"][1][0]].role == "pantry"), None)
    if addon is None and len(best["lines"]) > 1:
        addon = next((e for e in feasible if e["lines"] == best["lines"][:1]), None)
        add_alt("remove_addon", "Same main without the add-on", addon, "Drops the add-on to save cost.")
    else:
        add_alt("addition", "Add a previously purchased food", addon,
                "Adds a pantry food that appears in the purchase history.")
    target_progress = 0.6
    saver = [e for e in feasible if e["scores"]["goal_progress"] >= target_progress]
    saver = min(saver or feasible, key=lambda e: (e["cost"]["total"], -e["scores"]["total"]))
    add_alt("budget_saver", "Lowest-cost option", saver,
            f"Cheapest feasible option reaching at least {int(target_progress * 100)}% goal progress.")

    rec = _strip(best) | {"reasons": reasons(best, ctx), "confidence": confidence(best, ctx)}
    ranking = [{"rank": i + 1, "name": e["name"], "cost_inr": e["cost"]["total"],
                "goal_amount": e["goal_contribution"]["amount"], "calories": e["nutrients"]["calories_kcal"],
                "goal_score": e["scores"]["goal"], "preference_score": e["scores"]["preference"],
                "cost_score": e["scores"]["cost"], "total_score": e["scores"]["total"],
                "lines": [{"food_id": f, "servings": s} for f, s in e["lines"]]}
               for i, e in enumerate(feasible[:top_n])]
    return base | {"recommended": rec, "alternatives": alts, "ranking": ranking}


def context_payload(ctx: Context) -> dict:
    return {"meal_type": ctx.meal_type, "source": ctx.source, "goal": ctx.goal, "meal_share": ctx.meal_share,
            "meal_target": round(ctx.meal_target, 1), "kcal_allowance": round(ctx.kcal_allowance),
            "daily_kcal_reference": ctx.daily_kcal, "budget": ctx.budget, "weights": ctx.weights,
            "reference_date": ctx.reference_date.date().isoformat(), "recent_intake": ctx.recent,
            "latest_weight_kg": latest_weight(ctx.ds),
            "availability_note": "Options come from the dataset's meal-option list; real-time local "
                                 "availability is not represented.",
            "price_note": "Prices are the latest observed in historical (synthetic) records, not current prices."}


# ----------------------------------------------------------------------------- scenarios
def _parse_lines(raw: list[dict], ctx: Context) -> list[tuple[str, float]]:
    lines: list[tuple[str, float]] = []
    for r in raw:
        fid = r.get("food_id")
        if fid not in ctx.foods:
            raise ScenarioError(f"food '{fid}' has no nutrition/price data in the meal options")
        s = float(r.get("servings", 1))
        if not MIN_SERVINGS <= s <= MAX_SERVINGS:
            raise ScenarioError(f"servings for {fid} must be between {MIN_SERVINGS} and {MAX_SERVINGS}")
        if any(f == fid for f, _ in lines):
            raise ScenarioError(f"food '{fid}' appears twice; combine servings instead")
        lines.append((fid, s))
    if not lines:
        raise ScenarioError("a meal needs at least one item")
    return lines


def apply_operations(lines: list[tuple[str, float]], ops: list[dict], ctx: Context) -> tuple[list, list[str]]:
    cur = list(lines)
    log = []
    for op in ops:
        kind, fid = op.get("op"), op.get("food_id")
        idx = next((i for i, (f, _) in enumerate(cur) if f == fid), None)
        if kind == "set_servings":
            if idx is None:
                raise ScenarioError(f"{fid} is not in the meal")
            s = float(op["servings"])
            if not MIN_SERVINGS <= s <= MAX_SERVINGS:
                raise ScenarioError(f"servings must be between {MIN_SERVINGS} and {MAX_SERVINGS}")
            log.append(f"Changed {ctx.foods[fid].name} from {cur[idx][1]:g} to {s:g} serving(s)")
            cur[idx] = (fid, s)
        elif kind == "add":
            if fid not in ctx.foods:
                raise ScenarioError(f"food '{fid}' has no nutrition/price data")
            if idx is not None:
                raise ScenarioError(f"{fid} is already in the meal; use set_servings")
            s = float(op.get("servings", 1))
            if not MIN_SERVINGS <= s <= MAX_SERVINGS:
                raise ScenarioError(f"servings must be between {MIN_SERVINGS} and {MAX_SERVINGS}")
            cur.append((fid, s))
            log.append(f"Added {s:g} serving(s) of {ctx.foods[fid].name}")
        elif kind == "remove":
            if idx is None:
                raise ScenarioError(f"{fid} is not in the meal")
            log.append(f"Removed {ctx.foods[fid].name}")
            cur.pop(idx)
        elif kind == "substitute":
            new = op.get("with_food_id")
            if idx is None:
                raise ScenarioError(f"{fid} is not in the meal")
            if new not in ctx.foods:
                raise ScenarioError(f"food '{new}' has no nutrition/price data")
            if any(f == new for f, _ in cur):
                raise ScenarioError(f"{new} is already in the meal")
            s = float(op.get("servings", cur[idx][1]))
            log.append(f"Substituted {ctx.foods[fid].name} with {s:g} serving(s) of {ctx.foods[new].name}")
            cur[idx] = (new, s)
        else:
            raise ScenarioError("op must be one of set_servings, add, remove, substitute")
    if not cur:
        raise ScenarioError("the modified meal has no items left")
    return cur, log


def simulate(ds: Dataset, baseline: list[dict], operations: list[dict] | None = None,
             modified: list[dict] | None = None, meal_type: str = "lunch", goal_key: str = "protein",
             budget: float = DEFAULT_BUDGET, target_override: float | None = None) -> dict:
    """Compare a baseline meal with a modified one. All values are recalculated from reference data."""
    ctx = make_context(ds, meal_type, goal_key, budget, None, target_override)
    base_lines = _parse_lines(baseline, ctx)
    if modified is not None:
        mod_lines, log = _parse_lines(modified, ctx), ["Modified meal supplied directly"]
    else:
        mod_lines, log = apply_operations(base_lines, operations or [], ctx)
    b, m = evaluate(base_lines, ctx), evaluate(mod_lines, ctx)
    excluded = {e["food_id"]: e for e in exclusions(ctx)}
    warnings = [f"{ctx.foods[f].name} is labelled '{excluded[f]['latest_label']}' in feedback"
                for f, _ in mod_lines if f in excluded]
    warnings += [f"{ctx.foods[f].name} is not listed for {meal_type} in the dataset"
                 for f, _ in mod_lines if meal_type not in ctx.foods[f].meal_types]
    g = ctx.goal["nutrient"]
    diff = {n: round(m["nutrients"][n] - b["nutrients"][n], 1) for n in NUTRIENTS}
    if ctx.goal["direction"] == "at_least":
        delta = diff[g]
    else:
        delta = m["scores"]["goal_progress"] - b["scores"]["goal_progress"]
    goal_name = ctx.goal["goal_name"]
    verdict = (f"The change moves toward the goal '{goal_name}'" if delta > 0 else
               f"The change moves away from the goal '{goal_name}'" if delta < 0 else
               f"The change does not affect the goal '{goal_name}'")
    return {
        "context": context_payload(ctx), "operations_applied": log, "warnings": warnings,
        "baseline": _strip(b | {"lines": base_lines}), "modified": _strip(m | {"lines": mod_lines}),
        "differences": {
            "nutrients": diff, "cost": round(m["cost"]["total"] - b["cost"]["total"], 2),
            "goal_progress_pct_points": round((m["scores"]["goal_progress"] - b["scores"]["goal_progress"]) * 100, 1),
            "total_score": round(m["scores"]["total"] - b["scores"]["total"], 4),
        },
        "verdict": {
            "goal_direction": verdict,
            "baseline_within_budget": b["budget"]["within_budget"],
            "modified_within_budget": m["budget"]["within_budget"],
        },
        "assumptions": ["Prices and nutrients scale linearly with servings.",
                        "Each delivery vendor in the meal is a separate order with its own estimated fees.",
                        "Pantry foods are costed at their latest grocery price prorated to the serving."],
        "disclaimer": DISCLAIMER,
    }


def budget_comparison(ds: Dataset, budget: float, meal_type: str = "lunch", goal_key: str = "protein",
                      weights: dict | None = None, target_override: float | None = None, top_n: int = 8,
                      source: str = "any") -> dict:
    ctx = make_context(ds, meal_type, goal_key, budget, weights, target_override, source)
    feasible, over = rank(ctx)
    # One row per distinct main dish keeps the comparison readable.
    seen, rows = set(), []
    for e in feasible:
        if e["lines"][0][0] in seen:
            continue
        seen.add(e["lines"][0][0])
        rows.append(e)
        if len(rows) >= top_n:
            break
    fmt = lambda e, ok: {  # noqa: E731
        "name": e["name"], "feasible": ok, "lines": [{"food_id": f, "servings": s} for f, s in e["lines"]],
        "cost": e["cost"], "budget": e["budget"], "nutrients": e["nutrients"],
        "nutrients_missing": e["nutrients_missing"], "goal_contribution": e["goal_contribution"],
        "preference_score": e["scores"]["preference"], "scores": e["scores"],
        "main_rating": e["items"][0]["preference"]["mean_rating"]}
    return {
        "context": context_payload(ctx), "feasible_count": len(feasible), "over_budget_count": len(over),
        "options": [fmt(e, True) for e in rows],
        "nearest_over_budget": [fmt(e, False) for e in over[:3]],
        "cheapest_candidate_cost": min([e["cost"]["total"] for e in feasible + over], default=None),
        "note": "A higher cost does not imply a better nutritional outcome; compare goal contribution "
                "and calories directly.",
        "disclaimer": DISCLAIMER,
    }


METHOD = {
    "summary": "Transparent weighted score over feasible candidates (no machine learning).",
    "formulas": {
        "meal_target": "daily goal target x meal share",
        "goal_progress": "min(goal nutrient / meal_target, 1) for 'at least' goals; calorie fit for the calorie goal",
        "calorie_fit": "1 when 60-100% of the meal calorie allowance; proportional below 60%; "
                       "declines linearly to 0 at 200% of the allowance",
        "goal_score": "0.7 x goal_progress + 0.3 x secondary (calorie fit, or protein progress for the calorie goal)",
        "preference_score": "(adjusted rating - 1) / 4 where adjusted = (n x mean + 2 x overall mean) / (n + 2); "
                            "0.5 when no feedback; 0.75 main + 0.25 add-on",
        "cost_score": "1 - cost / budget",
        "total": "w_goal x goal_score + w_preference x preference_score + w_cost x cost_score",
        "cost": "items subtotal + vendor tax + estimated delivery/platform fees per delivery vendor",
    },
    "constraints": ["cost <= budget", "food listed for the selected meal type",
                    "latest explicit label is not 'disliked' or 'avoid'"],
    "tie_break": "higher total score, then higher preference score, then lower cost, then name",
    "meal_shares": MEAL_SHARES,
}

DISCLAIMER = ("Decision-support estimate from synthetic data. It does not diagnose, treat or prevent any "
              "condition, does not guarantee any health outcome, and is not a substitute for advice from a "
              "qualified clinician or dietitian.")
