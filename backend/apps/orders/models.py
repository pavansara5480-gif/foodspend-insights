from django.db import models
from django.db.models import F, Q

from apps.catalog.models import MEAL_TYPES, UNITS, Food, Vendor
from apps.health.models import Person


class Order(models.Model):
    """A purchase transaction or a logged home meal. Order-level charges live here, never on items."""
    RECORD_TYPES = [("delivery_order", "Delivery order"), ("cafe_purchase", "Cafe purchase"),
                    ("grocery_purchase", "Grocery purchase"), ("home_meal", "Home-prepared meal (estimated cost)")]
    order_id = models.CharField(primary_key=True, max_length=12)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="orders")
    order_datetime = models.DateTimeField()
    order_date = models.DateField(db_index=True)
    meal_type = models.CharField(max_length=15, choices=MEAL_TYPES + [("not_applicable", "Not a meal")])
    meal_type_inferred = models.BooleanField(default=False)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="orders")
    items_subtotal_inr = models.DecimalField(max_digits=10, decimal_places=2)
    order_discount_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_total_inr = models.DecimalField(max_digits=10, decimal_places=2)
    total_recomputed = models.BooleanField(default=False)
    counts_as_spending = models.BooleanField(default=True)

    class Meta:
        db_table = "orders"
        ordering = ["-order_datetime"]
        constraints = [
            models.CheckConstraint(condition=Q(items_subtotal_inr__gte=0, order_discount_inr__gte=0, tax_inr__gte=0,
                                               delivery_fee_inr__gte=0, other_charges_inr__gte=0),
                                   name="order_amounts_non_negative"),
            models.CheckConstraint(
                condition=Q(final_total_inr=F("items_subtotal_inr") - F("order_discount_inr") + F("tax_inr")
                            + F("delivery_fee_inr") + F("other_charges_inr")),
                name="order_final_total_consistent"),
        ]


class OrderItem(models.Model):
    CONSUMPTION = [("consumed", "Consumed"), ("partially_consumed", "Partially consumed"),
                   ("not_consumed", "Not consumed"), ("unknown", "Unknown")]
    order_item_id = models.CharField(primary_key=True, max_length=12)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.PROTECT, related_name="order_items")
    food_name_raw = models.CharField(max_length=160, blank=True, default="")
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    serving_size = models.DecimalField(max_digits=8, decimal_places=2)
    serving_unit = models.CharField(max_length=4, choices=UNITS)
    unit_price_inr = models.DecimalField(max_digits=10, decimal_places=2)
    item_discount_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total_inr = models.DecimalField(max_digits=10, decimal_places=2)
    consumption_status = models.CharField(max_length=20, choices=CONSUMPTION, default="unknown")
    portion_consumed = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    food_match_method = models.CharField(max_length=20, default="food_id")

    class Meta:
        db_table = "order_items"
        ordering = ["order_item_id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="item_quantity_positive"),
            models.CheckConstraint(condition=Q(serving_size__gt=0), name="item_serving_positive"),
            models.CheckConstraint(condition=Q(unit_price_inr__gte=0, item_discount_inr__gte=0), name="item_price_valid"),
            models.CheckConstraint(condition=Q(portion_consumed__isnull=True)
                                   | Q(portion_consumed__gte=0, portion_consumed__lte=1), name="item_portion_0_1"),
        ]
