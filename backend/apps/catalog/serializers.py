from rest_framework import serializers

from .models import Food, MealOption, NutritionReference, Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = "__all__"


class NutritionSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food.food_name", read_only=True)

    class Meta:
        model = NutritionReference
        fields = "__all__"


class MealOptionSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food.food_name", read_only=True)
    category = serializers.CharField(source="food.category", read_only=True)
    role = serializers.CharField(source="food.role", read_only=True)
    vendor_name = serializers.CharField(source="food.vendor.vendor_name", read_only=True)

    class Meta:
        model = MealOption
        fields = "__all__"


class FoodSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    channel = serializers.CharField(source="vendor.channel", read_only=True)
    nutrition = NutritionSerializer(read_only=True)

    class Meta:
        model = Food
        fields = ["food_id", "food_name", "category", "role", "vendor", "vendor_name", "channel",
                  "default_serving_size", "serving_unit", "description", "is_active", "nutrition"]


class FoodDetailSerializer(FoodSerializer):
    meal_options = MealOptionSerializer(many=True, read_only=True)

    class Meta(FoodSerializer.Meta):
        fields = FoodSerializer.Meta.fields + ["meal_options"]
