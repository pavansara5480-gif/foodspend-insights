from django.db import models
from django.db.models import Q

INDICATORS = [("weight", "Weight"), ("waist_circumference", "Waist circumference"),
              ("systolic_bp", "Systolic blood pressure"), ("diastolic_bp", "Diastolic blood pressure"),
              ("fasting_glucose", "Fasting glucose")]

# Plausibility bounds used to validate imported and API-submitted measurements.
PLAUSIBLE_RANGES = {"weight": (30, 250), "waist_circumference": (50, 200), "systolic_bp": (70, 250),
                    "diastolic_bp": (40, 150), "fasting_glucose": (40, 400)}
INDICATOR_UNITS = {"weight": "kg", "waist_circumference": "cm", "systolic_bp": "mmHg", "diastolic_bp": "mmHg",
                   "fasting_glucose": "mg/dL"}


class Person(models.Model):
    """The (synthetic) person whose data is analysed. Not a login account."""
    person_id = models.CharField(primary_key=True, max_length=10)
    display_name = models.CharField(max_length=120)
    sex = models.CharField(max_length=10, blank=True, default="")
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1)
    activity_level = models.CharField(max_length=20, blank=True, default="")
    is_synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        constraints = [models.CheckConstraint(condition=Q(height_cm__gt=50, height_cm__lt=260), name="person_height_valid")]

    def __str__(self):
        return self.display_name


class HealthMeasurement(models.Model):
    measurement_id = models.CharField(primary_key=True, max_length=12)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="measurements")
    measurement_date = models.DateField(db_index=True)
    indicator = models.CharField(max_length=30, choices=INDICATORS)
    value = models.DecimalField(max_digits=7, decimal_places=2)
    unit = models.CharField(max_length=10)
    source = models.CharField(max_length=120, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "health_measurements"
        ordering = ["measurement_date", "indicator"]
        constraints = [
            models.UniqueConstraint(fields=["person", "measurement_date", "indicator"], name="measurement_unique_per_day"),
            models.CheckConstraint(condition=Q(value__gt=0), name="measurement_value_positive"),
        ]


class NutritionGoal(models.Model):
    DIRECTIONS = [("at_least", "At least"), ("at_most", "At most")]
    goal_id = models.CharField(primary_key=True, max_length=10)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="goals")
    goal_key = models.CharField(max_length=20)
    goal_name = models.CharField(max_length=120)
    nutrient = models.CharField(max_length=20)
    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    target_value = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=20)
    reference_source = models.CharField(max_length=500)
    reference_date = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "nutrition_goals"
        constraints = [
            models.UniqueConstraint(fields=["person", "goal_key"], name="goal_unique_per_person"),
            models.CheckConstraint(condition=Q(target_value__gt=0), name="goal_target_positive"),
        ]


class ReferenceRange(models.Model):
    indicator = models.CharField(primary_key=True, max_length=30)
    lower = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    upper = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20)
    source = models.CharField(max_length=500)

    class Meta:
        db_table = "reference_ranges"
