from django.db import models
from django.db.models import Q

UNITS = [("g", "grams"), ("ml", "millilitres")]
MEAL_TYPES = [("breakfast", "Breakfast"), ("lunch", "Lunch"), ("snack", "Snack"), ("dinner", "Dinner")]


class Vendor(models.Model):
    CHANNELS = [("delivery", "Delivery restaurant"), ("cafe", "Cafe / takeaway"), ("grocery", "Grocery"),
                ("home", "Home kitchen")]
    vendor_id = models.CharField(primary_key=True, max_length=10)
    vendor_name = models.CharField(max_length=120, unique=True)
    channel = models.CharField(max_length=10, choices=CHANNELS)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    typical_delivery_fee_inr = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        db_table = "vendors"
        constraints = [models.CheckConstraint(condition=Q(tax_rate__gte=0, tax_rate__lt=1), name="vendor_tax_rate_valid")]

    def __str__(self):
        return self.vendor_name


class Food(models.Model):
    ROLES = [("main", "Main dish"), ("side", "Side"), ("pantry", "Pantry / grocery"), ("snack", "Snack"),
             ("beverage", "Beverage")]
    food_id = models.CharField(primary_key=True, max_length=10)
    food_name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=60, db_index=True)
    role = models.CharField(max_length=10, choices=ROLES)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="foods")
    default_serving_size = models.DecimalField(max_digits=8, decimal_places=2)
    serving_unit = models.CharField(max_length=4, choices=UNITS)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "foods"
        ordering = ["food_id"]
        constraints = [models.CheckConstraint(condition=Q(default_serving_size__gt=0), name="food_serving_positive")]

    def __str__(self):
        return self.food_name


class NutritionReference(models.Model):
    """Nutrient values for `basis_quantity` `basis_unit` of a food. NULL = unknown (never zero-filled)."""
    BASES = [("per_serving", "Per serving"), ("per_100g", "Per 100 g"), ("per_100ml", "Per 100 ml")]
    nutrition_id = models.CharField(primary_key=True, max_length=10)
    food = models.OneToOneField(Food, on_delete=models.CASCADE, related_name="nutrition")
    basis = models.CharField(max_length=12, choices=BASES)
    basis_quantity = models.DecimalField(max_digits=8, decimal_places=2)
    basis_unit = models.CharField(max_length=4, choices=UNITS)
    calories_kcal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    protein_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    carbs_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    nutrition_source = models.CharField(max_length=255)
    source_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "food_nutrition"
        constraints = [
            models.CheckConstraint(condition=Q(basis_quantity__gt=0), name="nutrition_basis_positive"),
            *[models.CheckConstraint(condition=Q(**{f"{n}__gte": 0}) | Q(**{f"{n}__isnull": True}),
                                     name=f"nutrition_{n}_non_negative")
              for n in ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]],
        ]


class MealOption(models.Model):
    """A food that can be chosen for a meal type, with its estimated price per serving."""
    meal_option_id = models.CharField(primary_key=True, max_length=10)
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="meal_options")
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPES)
    serving_size = models.DecimalField(max_digits=8, decimal_places=2)
    serving_unit = models.CharField(max_length=4, choices=UNITS)
    price_per_serving_inr = models.DecimalField(max_digits=8, decimal_places=2)
    allowed_servings = models.CharField(max_length=40, default="1",
                                        help_text="Comma-separated serving multipliers, e.g. 1,1.5")
    availability_status = models.CharField(max_length=30, default="listed_in_dataset")
    price_source = models.CharField(max_length=255)
    price_date = models.DateField()

    class Meta:
        db_table = "meal_options"
        ordering = ["meal_option_id"]
        constraints = [
            models.UniqueConstraint(fields=["food", "meal_type"], name="meal_option_unique_food_meal"),
            models.CheckConstraint(condition=Q(price_per_serving_inr__gt=0), name="meal_option_price_positive"),
            models.CheckConstraint(condition=Q(serving_size__gt=0), name="meal_option_serving_positive"),
        ]
