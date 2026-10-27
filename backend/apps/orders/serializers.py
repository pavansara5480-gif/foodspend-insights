import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import MEAL_TYPES, Food, MealOption, Vendor
from apps.health.models import Person

from .models import Order, OrderItem

CENT = Decimal("0.01")
# Which vendors' foods may appear in each record type
ALLOWED_FOOD_VENDOR_CHANNELS = {"home_meal": {"home", "grocery"}, "grocery_purchase": {"grocery"}}


class OrderItemSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food.food_name", read_only=True)
    category = serializers.CharField(source="food.category", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["order_item_id", "food", "food_name", "category", "food_name_raw", "quantity", "serving_size",
                  "serving_unit", "unit_price_inr", "item_discount_inr", "line_total_inr", "consumption_status",
                  "portion_consumed", "food_match_method"]


class OrderSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["order_id", "order_datetime", "order_date", "meal_type", "meal_type_inferred", "record_type",
                  "vendor", "vendor_name", "items_subtotal_inr", "order_discount_inr", "tax_inr", "delivery_fee_inr",
                  "other_charges_inr", "final_total_inr", "total_recomputed", "counts_as_spending", "items"]


class NewItemSerializer(serializers.Serializer):
    food_id = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    serving_size = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"), required=False)
    consumption_status = serializers.ChoiceField(choices=[c[0] for c in OrderItem.CONSUMPTION], default="unknown")
    portion_consumed = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal("0"),
                                                max_value=Decimal("1"), required=False, allow_null=True)


class OrderCreateSerializer(serializers.Serializer):
    """Log a new order. Prices and totals are computed server-side from meal-option prices; client-supplied
    prices are not accepted."""
    order_datetime = serializers.DateTimeField()
    meal_type = serializers.ChoiceField(choices=[m[0] for m in MEAL_TYPES] + ["not_applicable"])
    record_type = serializers.ChoiceField(choices=[r[0] for r in Order.RECORD_TYPES])
    vendor_id = serializers.CharField()
    order_discount_inr = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), default=0)
    delivery_fee_inr = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), default=0)
    other_charges_inr = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), default=0)
    items = NewItemSerializer(many=True, allow_empty=False)

    def validate(self, data):
        try:
            vendor = Vendor.objects.get(pk=data["vendor_id"])
        except Vendor.DoesNotExist:
            raise serializers.ValidationError({"vendor_id": "unknown vendor"})
        rt = data["record_type"]
        if (rt == "grocery_purchase") != (data["meal_type"] == "not_applicable"):
            raise serializers.ValidationError({"meal_type": "use 'not_applicable' only for grocery purchases"})
        foods = {f.food_id: f for f in Food.objects.select_related("vendor").filter(
            food_id__in=[i["food_id"] for i in data["items"]])}
        for i in data["items"]:
            f = foods.get(i["food_id"])
            if f is None:
                raise serializers.ValidationError({"items": f"unknown food {i['food_id']}"})
            allowed = ALLOWED_FOOD_VENDOR_CHANNELS.get(rt)
            if allowed is None and f.vendor_id != vendor.vendor_id:
                raise serializers.ValidationError({"items": f"{f.food_name} is not sold by {vendor.vendor_name}"})
            if allowed is not None and f.vendor.channel not in allowed:
                raise serializers.ValidationError({"items": f"{f.food_name} cannot be part of a {rt}"})
            if not MealOption.objects.filter(food=f).exists():
                raise serializers.ValidationError({"items": f"no price data for {f.food_name}"})
            if i["consumption_status"] == "unknown" and i.get("portion_consumed") is not None:
                raise serializers.ValidationError({"items": "portion_consumed must be empty when consumption is unknown"})
        data["vendor"], data["foods"] = vendor, foods
        return data

    @transaction.atomic
    def create(self, data):
        vendor, foods = data["vendor"], data["foods"]
        order = Order(order_id="OA" + uuid.uuid4().hex[:9].upper(), person=Person.objects.first(),
                      order_datetime=data["order_datetime"], order_date=data["order_datetime"].date(),
                      meal_type=data["meal_type"], record_type=data["record_type"], vendor=vendor,
                      order_discount_inr=data["order_discount_inr"], delivery_fee_inr=data["delivery_fee_inr"],
                      other_charges_inr=data["other_charges_inr"], counts_as_spending=data["record_type"] != "home_meal",
                      items_subtotal_inr=0, tax_inr=0, final_total_inr=0)
        items, subtotal = [], Decimal("0")
        for n, i in enumerate(data["items"], 1):
            f = foods[i["food_id"]]
            opt = MealOption.objects.filter(food=f).order_by("-price_date").first()
            size = i.get("serving_size") or opt.serving_size
            unit_price = (opt.price_per_serving_inr * size / opt.serving_size).quantize(CENT, ROUND_HALF_UP)
            line = (i["quantity"] * unit_price).quantize(CENT, ROUND_HALF_UP)
            subtotal += line
            portion = i.get("portion_consumed")
            if portion is None:
                portion = {"consumed": Decimal("1"), "not_consumed": Decimal("0")}.get(i["consumption_status"])
            items.append(OrderItem(order_item_id=f"{order.order_id[:10]}{n:02d}", order=order, food=f,
                                   food_name_raw=f.food_name, quantity=i["quantity"], serving_size=size,
                                   serving_unit=f.serving_unit, unit_price_inr=unit_price, item_discount_inr=0,
                                   line_total_inr=line, consumption_status=i["consumption_status"],
                                   portion_consumed=portion, food_match_method="api"))
        if data["order_discount_inr"] > subtotal:
            raise serializers.ValidationError({"order_discount_inr": "discount cannot exceed the items subtotal"})
        taxable = vendor.channel in ("delivery", "cafe") and data["record_type"] in ("delivery_order", "cafe_purchase")
        tax = ((subtotal - data["order_discount_inr"]) * vendor.tax_rate).quantize(CENT, ROUND_HALF_UP) if taxable else Decimal("0")
        order.items_subtotal_inr, order.tax_inr = subtotal, tax
        order.final_total_inr = (subtotal - data["order_discount_inr"] + tax + data["delivery_fee_inr"]
                                 + data["other_charges_inr"])
        order.save()
        OrderItem.objects.bulk_create(items)
        from apps.analytics.services import invalidate
        invalidate()  # bulk_create bypasses post_save signals
        return order
