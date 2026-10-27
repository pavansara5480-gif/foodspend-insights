from django.db.models.signals import post_delete, post_save

from apps.catalog.models import Food, MealOption, NutritionReference, Vendor
from apps.health.models import HealthMeasurement, NutritionGoal, Person, ReferenceRange
from apps.orders.models import Order, OrderItem
from apps.preferences.models import FoodFeedback

from .services import invalidate

for model in (Vendor, Food, NutritionReference, MealOption, Person, HealthMeasurement, NutritionGoal,
              ReferenceRange, Order, OrderItem, FoodFeedback):
    post_save.connect(lambda **kw: invalidate(), sender=model, weak=False)
    post_delete.connect(lambda **kw: invalidate(), sender=model, weak=False)
