from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("health/measurements", views.MeasurementViewSet, basename="measurement")
router.register("goals", views.GoalViewSet, basename="goal")
router.register("reference-ranges", views.ReferenceRangeViewSet, basename="reference-range")
urlpatterns = [path("health/summary/", views.summary, name="health-summary")] + router.urls
