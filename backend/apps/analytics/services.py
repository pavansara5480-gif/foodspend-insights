"""Load the database into a foodspend_core Dataset so the API uses the same formulas as the notebooks.

The Dataset is cached per process and invalidated by model signals (see signals.py) and by the import
command, so analytics always reflect the current database state.
"""
from __future__ import annotations

import threading

import pandas as pd
from django.conf import settings

from apps.catalog.models import Food, MealOption, NutritionReference, Vendor
from apps.health.models import HealthMeasurement, NutritionGoal, Person, ReferenceRange
from apps.orders.models import Order, OrderItem
from apps.preferences.models import FoodFeedback
from foodspend_core.analytics import Dataset, normalise

_lock = threading.Lock()
_state = {"version": 0, "cached_version": -1, "dataset": None}


class NoDataError(RuntimeError):
    pass


def invalidate() -> None:
    with _lock:
        _state["version"] += 1


def _frame(qs, fields: list[str], rename: dict | None = None) -> pd.DataFrame:
    df = pd.DataFrame.from_records(list(qs.values(*fields)), columns=fields)
    return df.rename(columns=rename or {})


def _build(person_id: str) -> Dataset:
    if not Person.objects.filter(pk=person_id).exists():
        raise NoDataError(f"No data for person '{person_id}'. Run: python manage.py import_data")
    p = {"person_id": person_id}
    users = _frame(Person.objects.filter(pk=person_id),
                   ["person_id", "display_name", "sex", "birth_year", "height_cm", "activity_level", "is_synthetic"],
                   {"person_id": "user_id"})
    users["height_cm"] = users["height_cm"].astype(float)
    vendors = _frame(Vendor.objects.all(), ["vendor_id", "vendor_name", "channel", "tax_rate",
                                            "typical_delivery_fee_inr"])
    vendors[["tax_rate", "typical_delivery_fee_inr"]] = vendors[["tax_rate", "typical_delivery_fee_inr"]].astype(float)
    foods = _frame(Food.objects.all(), ["food_id", "food_name", "category", "role", "vendor_id",
                                        "default_serving_size", "serving_unit", "is_active"])
    nutrition = _frame(NutritionReference.objects.all(),
                       ["nutrition_id", "food_id", "basis", "basis_quantity", "basis_unit", "calories_kcal",
                        "protein_g", "carbs_g", "fat_g", "fiber_g", "nutrition_source", "source_date"])
    options = _frame(MealOption.objects.all(),
                     ["meal_option_id", "food_id", "meal_type", "serving_size", "serving_unit",
                      "price_per_serving_inr", "allowed_servings", "availability_status", "price_source",
                      "price_date"])
    for c in ["serving_size", "price_per_serving_inr"]:
        options[c] = options[c].astype(float)
    orders = _frame(Order.objects.filter(**p),
                    ["order_id", "person_id", "order_datetime", "order_date", "meal_type", "meal_type_inferred",
                     "record_type", "vendor_id", "items_subtotal_inr", "order_discount_inr", "tax_inr",
                     "delivery_fee_inr", "other_charges_inr", "final_total_inr", "total_recomputed",
                     "counts_as_spending"], {"person_id": "user_id"})
    items = _frame(OrderItem.objects.filter(order__person_id=person_id),
                   ["order_item_id", "order_id", "food_id", "food_name_raw", "quantity", "serving_size",
                    "serving_unit", "unit_price_inr", "item_discount_inr", "line_total_inr", "consumption_status",
                    "portion_consumed", "food_match_method"])
    feedback = _frame(FoodFeedback.objects.filter(**p),
                      ["feedback_id", "person_id", "food_id", "order_id", "feedback_date", "rating",
                       "preference_label", "comment", "would_buy_again", "serving_preference"],
                      {"person_id": "user_id"})
    health = _frame(HealthMeasurement.objects.filter(**p),
                    ["measurement_id", "person_id", "measurement_date", "indicator", "value", "unit", "source",
                     "notes"], {"person_id": "user_id"})
    goals = _frame(NutritionGoal.objects.filter(**p),
                   ["goal_id", "person_id", "goal_key", "goal_name", "nutrient", "direction", "target_value", "unit",
                    "reference_source", "reference_date", "is_active"], {"person_id": "user_id"})
    goals["target_value"] = goals["target_value"].astype(float)
    ranges = _frame(ReferenceRange.objects.all(), ["indicator", "lower", "upper", "unit", "source"])
    for c in ["lower", "upper"]:
        ranges[c] = pd.to_numeric(ranges[c], errors="coerce").astype(float)
    if orders.empty:
        raise NoDataError("The database has no orders. Run: python manage.py import_data")
    return normalise(Dataset(users=users, vendors=vendors, foods=foods, nutrition=nutrition, meal_options=options,
                             orders=orders, items=items, feedback=feedback, health=health, goals=goals,
                             ranges=ranges))


def get_dataset(person_id: str | None = None) -> Dataset:
    person_id = person_id or settings.DEFAULT_PERSON_ID
    with _lock:
        if _state["cached_version"] == _state["version"] and _state["dataset"] is not None \
                and _state.get("person") == person_id:
            return _state["dataset"]
        version = _state["version"]
    ds = _build(person_id)
    with _lock:
        _state.update(dataset=ds, cached_version=version, person=person_id)
    return ds
