import uuid

from django.db import models
from django.db.models import Q

from apps.catalog.models import Food
from apps.health.models import Person
from apps.orders.models import Order


def new_feedback_id() -> str:
    return "FBA" + uuid.uuid4().hex[:7].upper()


class FoodFeedback(models.Model):
    LABELS = [("liked", "Liked"), ("acceptable", "Acceptable"), ("disliked", "Disliked"), ("avoid", "Avoid")]
    YES_NO = [("yes", "Yes"), ("maybe", "Maybe"), ("no", "No")]
    SERVING = [("increase", "Increase"), ("same", "Same"), ("decrease", "Decrease")]

    feedback_id = models.CharField(primary_key=True, max_length=12, default=new_feedback_id)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="feedback")
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="feedback")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback")
    feedback_date = models.DateField(db_index=True)
    rating = models.PositiveSmallIntegerField()
    preference_label = models.CharField(max_length=12, choices=LABELS)
    comment = models.CharField(max_length=255, blank=True, default="")
    would_buy_again = models.CharField(max_length=6, choices=YES_NO, blank=True, default="")
    serving_preference = models.CharField(max_length=10, choices=SERVING, blank=True, default="")
    order_link_removed = models.BooleanField(default=False)
    created_via = models.CharField(max_length=10, default="import")

    class Meta:
        db_table = "food_feedback"
        ordering = ["-feedback_date", "-feedback_id"]
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="feedback_rating_1_5")]
