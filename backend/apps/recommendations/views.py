from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.analytics.params import get_choice, get_float
from apps.analytics.services import get_dataset
from apps.analytics.views import clean
from foodspend_core.constants import MEAL_SHARES
from foodspend_core.recommender import (DEFAULT_BUDGET, SOURCES, budget_comparison, recommend,
                                        simulate)

GOALS = {"protein", "fiber", "calories"}
MAX_BUDGET = 100000


def common(request):
    return {
        "meal_type": get_choice(request, "meal_type", set(MEAL_SHARES), "lunch"),
        "goal_key": get_choice(request, "goal", GOALS, "protein"),
        "budget": get_float(request, "budget", DEFAULT_BUDGET, 0, MAX_BUDGET),
        "target_override": get_float(request, "target", None, 0.1, 10000),
        "source": get_choice(request, "source", set(SOURCES), "any"),
    }


@api_view(["GET"])
def next_meal(request):
    """GET /api/recommendations/next-meal/?meal_type=lunch&goal=protein&budget=350&source=any
    &w_goal=0.5&w_pref=0.3&w_cost=0.2&target=65"""
    weights = {"goal": get_float(request, "w_goal", None, 0, 1), "preference": get_float(request, "w_pref", None, 0, 1),
               "cost": get_float(request, "w_cost", None, 0, 1)}
    return Response(clean(recommend(get_dataset(), weights=weights, **common(request))))


@api_view(["GET"])
def budget(request):
    """GET /api/scenarios/budget/?budget=250&meal_type=lunch&goal=protein&source=any"""
    return Response(clean(budget_comparison(get_dataset(), **common(request))))


@api_view(["GET"])
def sensitivity(request):
    """How the recommendation changes under different weight presets and budgets."""
    args = common(request)
    ds = get_dataset()
    presets = {"Balanced (default)": {"goal": 0.5, "preference": 0.3, "cost": 0.2},
               "Goal first": {"goal": 0.7, "preference": 0.2, "cost": 0.1},
               "Preference first": {"goal": 0.3, "preference": 0.6, "cost": 0.1},
               "Cost first": {"goal": 0.3, "preference": 0.2, "cost": 0.5}}
    by_weights = []
    for name, w in presets.items():
        r = recommend(ds, weights=w, **args)["recommended"]
        by_weights.append({"preset": name, "weights": w, "recommended": None if r is None else r["name"],
                           "cost": None if r is None else r["cost"]["total"],
                           "goal_amount": None if r is None else r["goal_contribution"]["amount"]})
    by_budget = []
    for b in [100, 150, 250, 350, 500]:
        r = recommend(ds, **{**args, "budget": b})["recommended"]
        by_budget.append({"budget": b, "recommended": None if r is None else r["name"],
                          "cost": None if r is None else r["cost"]["total"],
                          "goal_amount": None if r is None else r["goal_contribution"]["amount"],
                          "total_score": None if r is None else r["scores"]["total"]})
    return Response(clean({"context": {k: v for k, v in args.items()}, "by_weights": by_weights,
                           "by_budget": by_budget}))


class LineSerializer(serializers.Serializer):
    food_id = serializers.CharField()
    servings = serializers.FloatField(min_value=0.25, max_value=5)


class OperationSerializer(serializers.Serializer):
    op = serializers.ChoiceField(choices=["set_servings", "add", "remove", "substitute"])
    food_id = serializers.CharField()
    servings = serializers.FloatField(min_value=0.25, max_value=5, required=False)
    with_food_id = serializers.CharField(required=False)

    def validate(self, data):
        if data["op"] == "set_servings" and "servings" not in data:
            raise serializers.ValidationError("set_servings requires 'servings'")
        if data["op"] == "substitute" and not data.get("with_food_id"):
            raise serializers.ValidationError("substitute requires 'with_food_id'")
        return data


class SimulationSerializer(serializers.Serializer):
    meal_type = serializers.ChoiceField(choices=list(MEAL_SHARES), default="lunch")
    goal = serializers.ChoiceField(choices=sorted(GOALS), default="protein")
    budget = serializers.FloatField(min_value=0, max_value=MAX_BUDGET, default=DEFAULT_BUDGET)
    target = serializers.FloatField(min_value=0.1, max_value=10000, required=False, allow_null=True)
    baseline = LineSerializer(many=True, allow_empty=False)
    operations = OperationSerializer(many=True, required=False)
    modified = LineSerializer(many=True, required=False, allow_empty=False)

    def validate(self, data):
        if "operations" not in data and "modified" not in data:
            raise serializers.ValidationError("provide either 'operations' or 'modified'")
        return data


@api_view(["POST"])
def simulate_view(request):
    """POST /api/scenarios/simulate/ — recalculates baseline vs modified meal from reference data."""
    s = SimulationSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    result = simulate(get_dataset(), baseline=d["baseline"], operations=d.get("operations"),
                      modified=d.get("modified"), meal_type=d["meal_type"], goal_key=d["goal"], budget=d["budget"],
                      target_override=d.get("target"))
    return Response(clean(result))
