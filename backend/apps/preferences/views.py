from datetime import date

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.analytics.services import get_dataset
from apps.analytics.views import clean
from apps.health.models import Person
from foodspend_core.analytics import preference_summary, preference_table
from foodspend_core.constants import EXCLUDED_LABELS

from .models import FoodFeedback


class FeedbackSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food.food_name", read_only=True)
    feedback_date = serializers.DateField(default=date.today)

    class Meta:
        model = FoodFeedback
        fields = ["feedback_id", "food", "food_name", "order", "feedback_date", "rating", "preference_label",
                  "comment", "would_buy_again", "serving_preference", "order_link_removed", "created_via"]
        read_only_fields = ["feedback_id", "order_link_removed", "created_via"]

    def validate_rating(self, v):
        if not 1 <= v <= 5:
            raise serializers.ValidationError("rating must be between 1 and 5")
        return v

    def validate_feedback_date(self, v):
        if v > date.today():
            raise serializers.ValidationError("feedback_date cannot be in the future")
        return v

    def validate(self, data):
        rating = data.get("rating", getattr(self.instance, "rating", None))
        label = data.get("preference_label", getattr(self.instance, "preference_label", None))
        if label == "liked" and rating is not None and rating <= 2:
            raise serializers.ValidationError("a 'liked' label conflicts with a rating of 1-2")
        if label == "disliked" and rating is not None and rating >= 4:
            raise serializers.ValidationError("a 'disliked' label conflicts with a rating of 4-5")
        order = data.get("order")
        food = data.get("food", getattr(self.instance, "food", None))
        if order is not None and food is not None and not order.items.filter(food=food).exists():
            raise serializers.ValidationError({"order": "that order does not contain this food"})
        return data

    def create(self, data):
        return FoodFeedback.objects.create(person=Person.objects.first(), created_via="api", **data)


class FeedbackViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """GET/POST /api/feedback/   PATCH /api/feedback/{id}/   filters: food, label"""
    serializer_class = FeedbackSerializer

    def get_queryset(self):
        qs = FoodFeedback.objects.select_related("food")
        p = self.request.query_params
        if p.get("food"):
            qs = qs.filter(food_id=p["food"])
        if p.get("label"):
            qs = qs.filter(preference_label=p["label"])
        return qs


@api_view(["GET"])
def summary(request):
    ds = get_dataset()
    return Response(clean({"summary": preference_summary(ds), "foods": preference_table(ds),
                           "rating_scale": "1 (worst) to 5 (best)",
                           "groups": "Positive = latest label 'liked'; Neutral = 'acceptable'; Negative = 'disliked' "
                                     "or 'avoid'; No feedback = never rated (purchases are not used to infer liking)."}))


@api_view(["GET"])
def excluded(request):
    t = preference_table(get_dataset())
    rows = t[t["latest_label"].isin(EXCLUDED_LABELS)]
    return Response(clean({"excluded_labels": sorted(EXCLUDED_LABELS), "foods": rows}))
