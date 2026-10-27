"""Unit tests for the pure formulas (no database)."""
from django.test import SimpleTestCase

from foodspend_core.formulas import (UnitMismatch, budget_metrics, goal_status, line_total, nutrient_amounts,
                                     order_final_total)
from foodspend_core.recommender import calorie_fit


class NutrientScalingTests(SimpleTestCase):
    def test_per_100g_basis(self):
        r = nutrient_amounts(150, "g", 100, "g", {"calories_kcal": 61, "protein_g": 3.5, "carbs_g": 4.7,
                                                  "fat_g": 3.3, "fiber_g": 0})
        self.assertEqual(r["calories_kcal"], 91.5)
        self.assertEqual(r["protein_g"], 5.25)
        self.assertEqual(r["fiber_g"], 0)

    def test_per_serving_basis(self):
        r = nutrient_amounts(500, "g", 250, "g", {"calories_kcal": 420, "protein_g": 9, "carbs_g": 62,
                                                  "fat_g": 15, "fiber_g": 5})
        self.assertEqual(r["calories_kcal"], 840)

    def test_unknown_stays_none(self):
        r = nutrient_amounts(350, "g", 350, "g", {"calories_kcal": 610, "protein_g": 12, "carbs_g": 92,
                                                  "fat_g": 21, "fiber_g": None})
        self.assertIsNone(r["fiber_g"])

    def test_unit_mismatch_rejected(self):
        with self.assertRaises(UnitMismatch):
            nutrient_amounts(100, "ml", 100, "g", {"calories_kcal": 1})


class MoneyTests(SimpleTestCase):
    def test_order_total(self):
        self.assertEqual(order_final_total(200, 20, 9, 35, 5), 229.0)

    def test_line_total(self):
        self.assertEqual(line_total(2, 110, 10), 210.0)

    def test_budget_metrics(self):
        m = budget_metrics(250, 400)
        self.assertEqual(m["remaining"], 150)
        self.assertEqual(m["utilization_pct"], 62.5)
        self.assertTrue(m["within_budget"])

    def test_zero_budget_has_no_division_error(self):
        m = budget_metrics(50, 0)
        self.assertIsNone(m["utilization_pct"])
        self.assertFalse(m["within_budget"])


class StatusTests(SimpleTestCase):
    def test_at_least(self):
        self.assertEqual(goal_status(50, "at_least", target=65), "Below target")
        self.assertEqual(goal_status(80, "at_least", target=65), "Within range")

    def test_at_most(self):
        self.assertEqual(goal_status(2300, "at_most", target=2110), "Above target")

    def test_range_and_missing(self):
        self.assertEqual(goal_status(26.7, "range", lower=18.5, upper=24.9), "Above target")
        self.assertEqual(goal_status(None, "range", lower=18.5, upper=24.9), "Insufficient data")
        self.assertEqual(goal_status(70, "range"), "Insufficient data")

    def test_calorie_fit(self):
        self.assertEqual(calorie_fit(600, 700), 1.0)
        self.assertAlmostEqual(calorie_fit(210, 700), 0.5)
        self.assertEqual(calorie_fit(1400, 700), 0.0)
