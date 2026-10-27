import uuid
from datetime import date

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.analytics.params import get_choice, period
from apps.analytics.services import get_dataset
from apps.analytics.views import clean
from foodspend_core.analytics import filter_period, health_series, health_summary, latest_weight

from .models import INDICATOR_UNITS, PLAUSIBLE_RANGES, HealthMeasurement, NutritionGoal, Person, ReferenceRange


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMeasurement
        fields = ["measurement_id", "measurement_date", "indicator", "value", "unit", "source", "notes"]
        read_only_fields = ["measurement_id", "unit"]

    def validate(self, data):
        ind, v = data["indicator"], data["value"]
        lo, hi = PLAUSIBLE_RANGES[ind]
        if not lo <= v <= hi:
            raise serializers.ValidationError({"value": f"{ind} must be between {lo} and {hi} {INDICATOR_UNITS[ind]}"})
        if data["measurement_date"] > date.today():
            raise serializers.ValidationError({"measurement_date": "cannot be in the future"})
        person = Person.objects.first()
        if HealthMeasurement.objects.filter(person=person, measurement_date=data["measurement_date"],
                                            indicator=ind).exists():
            raise serializers.ValidationError("a measurement for this indicator and date already exists")
        return data

    def create(self, data):
        return HealthMeasurement.objects.create(
            measurement_id="HA" + uuid.uuid4().hex[:8].upper(), person=Person.objects.first(),
            unit=INDICATOR_UNITS[data["indicator"]], **data)


class MeasurementViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """GET /api/health/measurements/?indicator=&start=&end=   POST to add a measurement."""
    serializer_class = MeasurementSerializer
    pagination_class = None

    def get_queryset(self):
        qs = HealthMeasurement.objects.all()
        ind = get_choice(self.request, "indicator", set(PLAUSIBLE_RANGES))
        start, end = period(self.request)
        if ind:
            qs = qs.filter(indicator=ind)
        if start:
            qs = qs.filter(measurement_date__gte=start)
        if end:
            qs = qs.filter(measurement_date__lte=end)
        return qs


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionGoal
        exclude = ["person"]


class ReferenceRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceRange
        fields = "__all__"


class GoalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NutritionGoal.objects.all().order_by("goal_id")
    serializer_class = GoalSerializer
    pagination_class = None


class ReferenceRangeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReferenceRange.objects.all()
    serializer_class = ReferenceRangeSerializer
    pagination_class = None


@api_view(["GET"])
def summary(request):
    start, end = period(request)
    ds = get_dataset()
    ds_p = filter_period(ds, start, end) if (start or end) else ds
    person = ds.users.iloc[0]
    return Response(clean({
        "person": {"display_name": person["display_name"], "height_cm": person["height_cm"],
                   "is_synthetic": True, "latest_weight_kg": latest_weight(ds)},
        "indicators": health_summary(ds_p),
        "series": health_series(ds_p),
        "notes": ["All measurements are simulated.", "BMI is derived from each weight reading and the recorded height.",
                  "Status labels compare the latest value with the documented reference range only; they are not "
                  "diagnoses.", "Changes over time are not attributed to food choices."],
    }))
