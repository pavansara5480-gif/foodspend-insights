"""Integration tests: import the processed dataset, then verify API values against independent pandas
calculations on the CSV files."""
from io import StringIO

import pandas as pd
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.analytics.services import invalidate
from apps.orders.models import Order, OrderItem

DATA = settings.DATA_DIR / "processed"


class ApiTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_data", no_report=True, stdout=StringIO())
        cls.orders = pd.read_csv(DATA / "orders.csv")
        cls.items = pd.read_csv(DATA / "order_items.csv")
        cls.nutrition = pd.read_csv(DATA / "food_nutrition.csv")

    def setUp(self):
        invalidate()
        self.c = APIClient()

    def get(self, url, status=200):
        r = self.c.get(url)
        self.assertEqual(r.status_code, status, r.content[:500])
        return r.json()


class ImportTests(ApiTestBase):
    def test_counts_match_csv(self):
        self.assertEqual(Order.objects.count(), len(self.orders))
        self.assertEqual(OrderItem.objects.count(), len(self.items))

    def test_import_is_idempotent(self):
        call_command("import_data", no_report=True, stdout=StringIO())
        self.assertEqual(Order.objects.count(), len(self.orders))
        self.assertEqual(OrderItem.objects.count(), len(self.items))


class SpendingTests(ApiTestBase):
    def test_total_spending_matches_independent_calculation(self):
        expected = self.orders.loc[self.orders["record_type"] != "home_meal", "final_total_inr"].sum()
        d = self.get("/api/analytics/spending/")
        self.assertAlmostEqual(d["summary"]["total_spending_inr"], round(expected, 2), places=2)

    def test_category_breakdown_reconciles_to_total(self):
        d = self.get("/api/analytics/spending/")
        self.assertAlmostEqual(sum(r["spending_inr"] for r in d["by_category"]),
                               d["summary"]["total_spending_inr"], delta=0.1)

    def test_no_join_duplication(self):
        d = self.get("/api/analytics/data-quality/")["live_checks"]
        self.assertGreater(d["join_duplication_check"]["naive_item_join_total"],
                           d["join_duplication_check"]["correct_order_level_total"])
        self.assertEqual(d["orders_where_item_lines_differ_from_subtotal"], 0)

    def test_period_filter(self):
        d = self.get("/api/analytics/spending/?start=2026-01-01&end=2026-01-31")
        o = self.orders[(self.orders["order_date"] >= "2026-01-01") & (self.orders["order_date"] <= "2026-01-31")
                        & (self.orders["record_type"] != "home_meal")]
        self.assertAlmostEqual(d["summary"]["total_spending_inr"], round(o["final_total_inr"].sum(), 2), places=2)

    def test_invalid_period(self):
        d = self.get("/api/analytics/spending/?start=2026-05-01&end=2026-01-01", 400)
        self.assertIn("error", d)


class NutritionTests(ApiTestBase):
    def test_daily_consumed_calories_match_pandas(self):
        it = self.items.merge(self.nutrition, on="food_id").merge(self.orders[["order_id", "order_date", "record_type"]],
                                                                  on="order_id")
        it = it[it["record_type"] != "grocery_purchase"]
        it["kcal"] = it["quantity"] * it["serving_size"] / it["basis_quantity"] * it["calories_kcal"] * it["portion_consumed"]
        daily = it.groupby("order_date")["kcal"].sum(min_count=1)
        d = self.get("/api/analytics/nutrition/")
        self.assertAlmostEqual(d["summary"]["average_daily_logged"]["calories_kcal"], round(daily.mean(), 1), places=1)

    def test_unknown_fiber_is_reported_not_zero(self):
        d = self.get("/api/analytics/nutrition/")
        self.assertIn("F013", d["summary"]["completeness"]["foods_with_unknown_nutrients"])
        self.assertGreater(d["summary"]["completeness"]["meal_items_unknown_fiber"], 0)

    def test_history_pagination_and_filter(self):
        d = self.get("/api/history/?category=Biryani&page_size=10&page=1")
        self.assertLessEqual(len(d["results"]), 10)
        self.assertTrue(all(r["category"] == "Biryani" for r in d["results"]))
        unknown = self.get("/api/history/?consumption=unknown&page_size=5")["results"]
        self.assertTrue(all(r["consumed_calories_kcal"] is None for r in unknown))


class RecommendationTests(ApiTestBase):
    def test_respects_budget_and_exclusions(self):
        d = self.get("/api/recommendations/next-meal/?meal_type=lunch&goal=protein&budget=200")
        rec = d["recommended"]
        self.assertLessEqual(rec["cost"]["total"], 200)
        excluded = {e["food_id"] for e in d["excluded_by_feedback"]}
        self.assertIn("F019", excluded)  # labelled 'avoid'
        for option in [rec] + d["alternatives"]:
            self.assertLessEqual(option["cost"]["total"], 200)
            self.assertFalse({l["food_id"] for l in option["lines"]} & excluded)
        self.assertGreaterEqual(len(d["alternatives"]), 2)

    def test_ranking_sorted(self):
        d = self.get("/api/recommendations/next-meal/?source=delivery&budget=400")
        totals = [r["total_score"] for r in d["ranking"]]
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertTrue(all(i["channel"] in ("delivery", "grocery") for i in d["recommended"]["items"]))

    def test_insufficient_budget_explains_instead_of_inventing(self):
        d = self.get("/api/recommendations/next-meal/?budget=10")
        self.assertIsNone(d["recommended"])
        self.assertIn("No option", d["message"])

    def test_invalid_inputs(self):
        self.get("/api/recommendations/next-meal/?budget=-1", 400)
        self.get("/api/recommendations/next-meal/?goal=sugar", 400)
        self.get("/api/recommendations/next-meal/?w_goal=0&w_pref=0&w_cost=0", 400)

    def test_new_dislike_excludes_food(self):
        d = self.get("/api/recommendations/next-meal/?budget=350")
        top_food = d["recommended"]["lines"][0]["food_id"]
        r = self.c.post("/api/feedback/", {"food": top_food, "rating": 1, "preference_label": "disliked",
                                           "feedback_date": "2026-10-26"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d2 = self.get("/api/recommendations/next-meal/?budget=350")
        self.assertNotEqual(d2["recommended"]["lines"][0]["food_id"], top_food)

    def test_budget_comparison(self):
        d = self.get("/api/scenarios/budget/?budget=250")
        self.assertTrue(all(o["cost"]["total"] <= 250 for o in d["options"]))
        self.assertTrue(all(o["cost"]["total"] > 250 for o in d["nearest_over_budget"]))
        o = d["options"][0]
        self.assertAlmostEqual(o["budget"]["remaining"], 250 - o["cost"]["total"], places=2)


class ScenarioTests(ApiTestBase):
    def post(self, body, status=200):
        r = self.c.post("/api/scenarios/simulate/", body, format="json")
        self.assertEqual(r.status_code, status, r.content[:500])
        return r.json()

    def test_serving_increase_doubles_item(self):
        d = self.post({"baseline": [{"food_id": "F027", "servings": 1}],
                       "operations": [{"op": "set_servings", "food_id": "F027", "servings": 2}]})
        self.assertAlmostEqual(d["modified"]["nutrients"]["protein_g"], 2 * d["baseline"]["nutrients"]["protein_g"])
        self.assertAlmostEqual(d["differences"]["cost"], d["baseline"]["cost"]["total"])  # home meal: no fees

    def test_add_pantry_food_uses_per_100g_basis(self):
        d = self.post({"baseline": [{"food_id": "F027", "servings": 1}],
                       "operations": [{"op": "add", "food_id": "F021", "servings": 1}]})
        n = self.nutrition.set_index("food_id").loc["F021"]
        self.assertAlmostEqual(d["differences"]["nutrients"]["protein_g"], round(150 / 100 * n["protein_g"], 1))

    def test_substitution_recalculates_tax_and_fees(self):
        d = self.post({"baseline": [{"food_id": "F004", "servings": 1}],
                       "operations": [{"op": "substitute", "food_id": "F004", "with_food_id": "F027"}]})
        self.assertEqual(d["modified"]["cost"]["fees"], 0)
        self.assertGreater(d["baseline"]["cost"]["fees"], 0)
        self.assertEqual(d["differences"]["cost"],
                         round(d["modified"]["cost"]["total"] - d["baseline"]["cost"]["total"], 2))

    def test_invalid_operations(self):
        self.post({"baseline": [{"food_id": "F004"}], "operations": [{"op": "remove", "food_id": "F004"}]}, 400)
        self.post({"baseline": [{"food_id": "F004"}], "operations": [{"op": "add", "food_id": "NOPE"}]}, 400)
        self.post({"baseline": [{"food_id": "F004", "servings": 9}], "operations": []}, 400)
        self.post({"baseline": [{"food_id": "F004"}]}, 400)


class ReadEndpointTests(ApiTestBase):
    def test_all_read_endpoints(self):
        for url in ["/api/foods/", "/api/foods/F004/", "/api/nutrition/", "/api/meal-options/?meal_type=lunch",
                    "/api/vendors/", "/api/orders/?meal_type=lunch", "/api/feedback/", "/api/preferences/summary/",
                    "/api/preferences/excluded/", "/api/health/measurements/?indicator=weight", "/api/health/summary/",
                    "/api/goals/", "/api/reference-ranges/", "/api/analytics/dashboard/", "/api/analytics/frequency/",
                    "/api/analytics/findings/", "/api/scenarios/sensitivity/"]:
            self.get(url)

    def test_health_measurement_validation(self):
        r = self.c.post("/api/health/measurements/", {"measurement_date": "2026-10-26", "indicator": "weight",
                                                      "value": 7.9}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/health/measurements/", {"measurement_date": "2026-10-26", "indicator": "weight",
                                                      "value": 78.6}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["unit"], "kg")

    def test_order_create_computes_prices_server_side(self):
        r = self.c.post("/api/orders/", {"order_datetime": "2026-10-26T13:00", "meal_type": "lunch",
                                         "record_type": "delivery_order", "vendor_id": "V02",
                                         "delivery_fee_inr": 35, "unit_price_inr": 1,
                                         "items": [{"food_id": "F005", "quantity": 1, "consumption_status": "consumed"}]},
                        format="json")
        self.assertEqual(r.status_code, 201, r.content)
        o = r.json()
        price = float(self.get("/api/foods/F005/")["meal_options"][0]["price_per_serving_inr"])
        self.assertAlmostEqual(float(o["items_subtotal_inr"]), price)
        self.assertAlmostEqual(float(o["final_total_inr"]), round(price * 1.05 + 35, 2), places=2)
