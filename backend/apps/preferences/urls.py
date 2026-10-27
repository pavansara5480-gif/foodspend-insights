from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("feedback", views.FeedbackViewSet, basename="feedback")
urlpatterns = [
    path("preferences/summary/", views.summary, name="preferences-summary"),
    path("preferences/excluded/", views.excluded, name="preferences-excluded"),
] + router.urls
