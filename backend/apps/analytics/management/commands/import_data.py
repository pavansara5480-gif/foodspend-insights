"""Import the cleaned CSVs (data/processed) into the database.

    python manage.py import_data [--data-dir PATH] [--dry-run]

* Validates required columns, identifiers, foreign keys, numeric ranges and allowed values.
* Rejected rows are reported with a reason (never silently dropped) and written to
  analysis/reports/import_report.json.
* Idempotent: rows are upserted by their stable primary keys, so repeating the import does not
  create duplicates. Everything runs in one transaction.
* After loading, database totals are reconciled against the CSV files.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Sum

from apps.analytics.services import invalidate
from apps.catalog.models import Food, MealOption, NutritionReference, Vendor
from apps.health.models import PLAUSIBLE_RANGES, HealthMeasurement, NutritionGoal, Person, ReferenceRange
from apps.orders.models import Order, OrderItem
from apps.preferences.models import FoodFeedback


class RowError(ValueError):
    pass


def dec(v, field, required=True, minimum=None, maximum=None):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        if required:
            raise RowError(f"{field} is required")
        return None
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise RowError(f"{field} is not a number: {v!r}")
    if minimum is not None and d < minimum:
        raise RowError(f"{field} must be >= {minimum}")
    if maximum is not None and d > maximum:
        raise RowError(f"{field} must be <= {maximum}")
    return d


def text(v, field, required=True, choices=None):
    s = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
    if required and not s:
        raise RowError(f"{field} is required")
    if choices is not None and s and s not in choices:
        raise RowError(f"{field}={s!r} is not one of {sorted(choices)}")
    return s


def boolean(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def date_(v, field, required=True):
    s = text(v, field, required)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except ValueError:
        raise RowError(f"{field} is not a valid date: {s!r}")


def choices(model, field):
    return {c[0] for c in model._meta.get_field(field).choices}


class Command(BaseCommand):
    help = "Validate and import data/processed/*.csv into the database (idempotent upsert)."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default=str(settings.DATA_DIR / "processed"))
        parser.add_argument("--dry-run", action="store_true", help="Validate only; roll back all writes.")
        parser.add_argument("--no-report", action="store_true", help="Do not write analysis/reports/import_report.json.")

    def handle(self, *args, **opts):
        self.dir = Path(opts["data_dir"])
        if not self.dir.exists():
            raise CommandError(f"{self.dir} does not exist. Run analysis/scripts/clean_data.py first.")
        self.rejected: list[dict] = []
        self.loaded: dict[str, int] = {}
        try:
            with transaction.atomic():
                self.run()
                self.reconcile()
                if opts["dry_run"]:
                    raise _DryRun()
        except _DryRun:
            self.stdout.write(self.style.WARNING("Dry run: all changes rolled back."))
        invalidate()
        report = {"run_at": datetime.now().isoformat(timespec="seconds"), "data_dir": str(self.dir),
                  "dry_run": opts["dry_run"], "database": connection.vendor, "loaded": self.loaded,
                  "rejected": self.rejected, "reconciliation": getattr(self, "recon", {})}
        if not opts["no_report"]:
            settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (settings.REPORTS_DIR / "import_report.json").write_text(json.dumps(report, indent=2, default=str),
                                                                     encoding="utf-8")
        for name, n in self.loaded.items():
            self.stdout.write(f"  {name:<22} {n:>6} rows upserted")
        self.stdout.write(f"  rejected rows: {len(self.rejected)}")
        for r in self.rejected[:20]:
            self.stdout.write(self.style.WARNING(f"    {r['table']} {r['record_id']}: {r['reason']}"))
        ok = all(v["match"] for v in report["reconciliation"].values())
        style = self.style.SUCCESS if ok else self.style.ERROR
        self.stdout.write(style(f"Reconciliation {'passed' if ok else 'FAILED'}: "
                                + ", ".join(f"{k}={v['database']}" for k, v in report["reconciliation"].items())))

    # ------------------------------------------------------------------ helpers
    def read(self, name: str, required: list[str]) -> pd.DataFrame:
        path = self.dir / f"{name}.csv"
        if not path.exists():
            raise CommandError(f"missing file {path}")
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise CommandError(f"{name}.csv missing columns {missing}")
        dup = df[required[0]].duplicated(keep="first")
        for rid in df.loc[dup, required[0]]:
            self.rejected.append({"table": name, "record_id": rid, "reason": "duplicate primary key in file"})
        return df[~dup]

    def build(self, name: str, df: pd.DataFrame, key: str, make) -> list:
        out = []
        for row in df.to_dict("records"):
            try:
                out.append(make(row))
            except RowError as e:
                self.rejected.append({"table": name, "record_id": row.get(key), "reason": str(e)})
        return out

    def upsert(self, model, objs: list, name: str) -> set:
        pk = model._meta.pk.name
        fields = [f.attname for f in model._meta.concrete_fields if not f.primary_key
                  and not getattr(f, "auto_now_add", False)]
        kw = {"update_conflicts": True, "update_fields": fields}
        if connection.features.supports_update_conflicts_with_target:
            kw["unique_fields"] = [pk]
        model.objects.bulk_create(objs, batch_size=500, **kw)
        self.loaded[name] = len(objs)
        return {getattr(o, pk) for o in objs}

    # ------------------------------------------------------------------ load
    def run(self):
        df = self.read("users", ["user_id", "display_name", "height_cm"])
        persons = self.upsert(Person, self.build("users", df, "user_id", lambda r: Person(
            person_id=text(r["user_id"], "user_id"), display_name=text(r["display_name"], "display_name"),
            sex=text(r.get("sex"), "sex", False), birth_year=int(r["birth_year"]) if r.get("birth_year") else None,
            height_cm=dec(r["height_cm"], "height_cm", minimum=50, maximum=260),
            activity_level=text(r.get("activity_level"), "activity_level", False),
            is_synthetic=boolean(r.get("is_synthetic", "true")))), "users")

        df = self.read("vendors", ["vendor_id", "vendor_name", "channel", "tax_rate"])
        vendors = self.upsert(Vendor, self.build("vendors", df, "vendor_id", lambda r: Vendor(
            vendor_id=text(r["vendor_id"], "vendor_id"), vendor_name=text(r["vendor_name"], "vendor_name"),
            channel=text(r["channel"], "channel", choices=choices(Vendor, "channel")),
            tax_rate=Decimal(text(r["tax_rate"], "tax_rate")),
            typical_delivery_fee_inr=dec(r.get("typical_delivery_fee_inr"), "typical_delivery_fee_inr", minimum=0)
            )), "vendors")

        def fk(value, valid: set, field):
            v = text(value, field)
            if v not in valid:
                raise RowError(f"{field}={v!r} does not exist")
            return v

        df = self.read("foods", ["food_id", "food_name", "category", "role", "vendor_id", "default_serving_size",
                                 "serving_unit"])
        foods = self.upsert(Food, self.build("foods", df, "food_id", lambda r: Food(
            food_id=text(r["food_id"], "food_id"), food_name=text(r["food_name"], "food_name"),
            category=text(r["category"], "category"), role=text(r["role"], "role", choices=choices(Food, "role")),
            vendor_id=fk(r["vendor_id"], vendors, "vendor_id"),
            default_serving_size=dec(r["default_serving_size"], "default_serving_size", minimum=Decimal("0.01")),
            serving_unit=text(r["serving_unit"], "serving_unit", choices={"g", "ml"}),
            is_active=boolean(r.get("is_active", "true")))), "foods")

        df = self.read("food_nutrition", ["nutrition_id", "food_id", "basis", "basis_quantity", "basis_unit"])
        self.upsert(NutritionReference, self.build("food_nutrition", df, "nutrition_id", lambda r: NutritionReference(
            nutrition_id=text(r["nutrition_id"], "nutrition_id"), food_id=fk(r["food_id"], foods, "food_id"),
            basis=text(r["basis"], "basis", choices=choices(NutritionReference, "basis")),
            basis_quantity=dec(r["basis_quantity"], "basis_quantity", minimum=Decimal("0.01")),
            basis_unit=text(r["basis_unit"], "basis_unit", choices={"g", "ml"}),
            **{n: dec(r.get(n), n, required=False, minimum=0)
               for n in ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]},
            nutrition_source=text(r.get("nutrition_source"), "nutrition_source"),
            source_date=date_(r.get("source_date"), "source_date", False))), "food_nutrition")

        df = self.read("meal_options", ["meal_option_id", "food_id", "meal_type", "serving_size",
                                        "price_per_serving_inr", "price_date"])
        self.upsert(MealOption, self.build("meal_options", df, "meal_option_id", lambda r: MealOption(
            meal_option_id=text(r["meal_option_id"], "meal_option_id"), food_id=fk(r["food_id"], foods, "food_id"),
            meal_type=text(r["meal_type"], "meal_type", choices=choices(MealOption, "meal_type")),
            serving_size=dec(r["serving_size"], "serving_size", minimum=Decimal("0.01")),
            serving_unit=text(r["serving_unit"], "serving_unit", choices={"g", "ml"}),
            price_per_serving_inr=dec(r["price_per_serving_inr"], "price_per_serving_inr", minimum=Decimal("0.01")),
            allowed_servings=text(r.get("allowed_servings"), "allowed_servings", False) or "1",
            availability_status=text(r.get("availability_status"), "availability_status", False) or "listed_in_dataset",
            price_source=text(r.get("price_source"), "price_source"),
            price_date=date_(r["price_date"], "price_date"))), "meal_options")

        def make_order(r):
            money = {f: dec(r[f], f, minimum=0) for f in ["items_subtotal_inr", "order_discount_inr", "tax_inr",
                                                           "delivery_fee_inr", "other_charges_inr", "final_total_inr"]}
            expected = (money["items_subtotal_inr"] - money["order_discount_inr"] + money["tax_inr"]
                        + money["delivery_fee_inr"] + money["other_charges_inr"])
            if expected != money["final_total_inr"]:
                raise RowError(f"final_total {money['final_total_inr']} != components {expected}")
            dt = datetime.fromisoformat(text(r["order_datetime"], "order_datetime"))
            return Order(order_id=text(r["order_id"], "order_id"), person_id=fk(r["user_id"], persons, "user_id"),
                         order_datetime=dt, order_date=dt.date(),
                         meal_type=text(r["meal_type"], "meal_type", choices=choices(Order, "meal_type")),
                         meal_type_inferred=boolean(r.get("meal_type_inferred")),
                         record_type=text(r["record_type"], "record_type", choices=choices(Order, "record_type")),
                         vendor_id=fk(r["vendor_id"], vendors, "vendor_id"),
                         total_recomputed=boolean(r.get("total_recomputed")),
                         counts_as_spending=r["record_type"] != "home_meal", **money)

        df = self.read("orders", ["order_id", "user_id", "order_datetime", "meal_type", "record_type", "vendor_id",
                                  "items_subtotal_inr", "order_discount_inr", "tax_inr", "delivery_fee_inr",
                                  "other_charges_inr", "final_total_inr"])
        orders = self.upsert(Order, self.build("orders", df, "order_id", make_order), "orders")

        def make_item(r):
            status = text(r["consumption_status"], "consumption_status", choices=choices(OrderItem, "consumption_status"))
            portion = dec(r.get("portion_consumed"), "portion_consumed", required=False, minimum=0, maximum=1)
            if status == "unknown" and portion is not None:
                raise RowError("portion_consumed must be blank when consumption is unknown")
            return OrderItem(
                order_item_id=text(r["order_item_id"], "order_item_id"), order_id=fk(r["order_id"], orders, "order_id"),
                food_id=fk(r["food_id"], foods, "food_id"), food_name_raw=text(r.get("food_name_raw"), "food_name_raw", False),
                quantity=dec(r["quantity"], "quantity", minimum=Decimal("0.01")),
                serving_size=dec(r["serving_size"], "serving_size", minimum=Decimal("0.01")),
                serving_unit=text(r["serving_unit"], "serving_unit", choices={"g", "ml"}),
                unit_price_inr=dec(r["unit_price_inr"], "unit_price_inr", minimum=0),
                item_discount_inr=dec(r.get("item_discount_inr") or 0, "item_discount_inr", minimum=0),
                line_total_inr=dec(r["line_total_inr"], "line_total_inr", minimum=0),
                consumption_status=status, portion_consumed=portion,
                food_match_method=text(r.get("food_match_method"), "food_match_method", False) or "food_id")

        df = self.read("order_items", ["order_item_id", "order_id", "food_id", "quantity", "serving_size",
                                       "serving_unit", "unit_price_inr", "line_total_inr", "consumption_status"])
        self.upsert(OrderItem, self.build("order_items", df, "order_item_id", make_item), "order_items")

        def make_feedback(r):
            rating = int(dec(r["rating"], "rating", minimum=1, maximum=5))
            order = text(r.get("order_id"), "order_id", False) or None
            if order is not None and order not in orders:
                raise RowError(f"order_id={order!r} does not exist")
            return FoodFeedback(
                feedback_id=text(r["feedback_id"], "feedback_id"), person_id=fk(r["user_id"], persons, "user_id"),
                food_id=fk(r["food_id"], foods, "food_id"), order_id=order,
                feedback_date=date_(r["feedback_date"], "feedback_date"), rating=rating,
                preference_label=text(r["preference_label"], "preference_label",
                                      choices=choices(FoodFeedback, "preference_label")),
                comment=text(r.get("comment"), "comment", False),
                would_buy_again=text(r.get("would_buy_again"), "would_buy_again", False, {"yes", "no", "maybe"}),
                serving_preference=text(r.get("serving_preference"), "serving_preference", False,
                                        {"increase", "same", "decrease"}),
                order_link_removed=boolean(r.get("order_link_removed")), created_via="import")

        df = self.read("food_feedback", ["feedback_id", "user_id", "food_id", "feedback_date", "rating",
                                         "preference_label"])
        self.upsert(FoodFeedback, self.build("food_feedback", df, "feedback_id", make_feedback), "food_feedback")

        def make_measure(r):
            ind = text(r["indicator"], "indicator", choices=set(PLAUSIBLE_RANGES))
            lo, hi = PLAUSIBLE_RANGES[ind]
            return HealthMeasurement(
                measurement_id=text(r["measurement_id"], "measurement_id"),
                person_id=fk(r["user_id"], persons, "user_id"),
                measurement_date=date_(r["measurement_date"], "measurement_date"), indicator=ind,
                value=dec(r["value"], "value", minimum=lo, maximum=hi), unit=text(r["unit"], "unit"),
                source=text(r.get("source"), "source", False), notes=text(r.get("notes"), "notes", False))

        df = self.read("health_measurements", ["measurement_id", "user_id", "measurement_date", "indicator", "value",
                                               "unit"])
        df = df[~df.duplicated(subset=["user_id", "measurement_date", "indicator"], keep="first")]
        self.upsert(HealthMeasurement, self.build("health_measurements", df, "measurement_id", make_measure),
                    "health_measurements")

        df = self.read("nutrition_goals", ["goal_id", "user_id", "goal_key", "nutrient", "direction", "target_value",
                                           "reference_source"])
        self.upsert(NutritionGoal, self.build("nutrition_goals", df, "goal_id", lambda r: NutritionGoal(
            goal_id=text(r["goal_id"], "goal_id"), person_id=fk(r["user_id"], persons, "user_id"),
            goal_key=text(r["goal_key"], "goal_key"), goal_name=text(r["goal_name"], "goal_name"),
            nutrient=text(r["nutrient"], "nutrient", choices={"calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"}),
            direction=text(r["direction"], "direction", choices=choices(NutritionGoal, "direction")),
            target_value=dec(r["target_value"], "target_value", minimum=Decimal("0.01")), unit=text(r["unit"], "unit"),
            reference_source=text(r["reference_source"], "reference_source"),
            reference_date=text(r.get("reference_date"), "reference_date", False),
            is_active=boolean(r.get("is_active")))), "nutrition_goals")

        df = self.read("reference_ranges", ["indicator", "unit", "source"])
        self.upsert(ReferenceRange, self.build("reference_ranges", df, "indicator", lambda r: ReferenceRange(
            indicator=text(r["indicator"], "indicator"), lower=dec(r.get("lower"), "lower", required=False),
            upper=dec(r.get("upper"), "upper", required=False), unit=text(r["unit"], "unit"),
            source=text(r["source"], "source"))), "reference_ranges")

    def reconcile(self):
        orders = pd.read_csv(self.dir / "orders.csv")
        items = pd.read_csv(self.dir / "order_items.csv")
        rejected_orders = {r["record_id"] for r in self.rejected if r["table"] == "orders"}
        rejected_items = {r["record_id"] for r in self.rejected if r["table"] == "order_items"}
        orders = orders[~orders["order_id"].isin(rejected_orders)]
        items = items[~items["order_item_id"].isin(rejected_items)]
        db_total = Order.objects.filter(counts_as_spending=True).aggregate(s=Sum("final_total_inr"))["s"] or 0
        csv_total = round(float(orders.loc[orders["record_type"] != "home_meal", "final_total_inr"].sum()), 2)
        db_lines =OrderItem.objects.aggregate(s=Sum("line_total_inr"))["s"] or 0
        self.recon = {
            "orders": {"csv": int(len(orders)), "database": Order.objects.count()},
            "order_items": {"csv": int(len(items)), "database": OrderItem.objects.count()},
            "spending_inr": {"csv": csv_total, "database": float(db_total)},
            "item_line_totals_inr": {"csv": round(float(items["line_total_inr"].sum()), 2), "database": float(db_lines)},
        }
        for v in self.recon.values():
            v["match"] = abs(float(v["csv"]) - float(v["database"])) < 0.01


class _DryRun(Exception):
    pass
