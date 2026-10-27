from django.urls import path

from . import views

urlpatterns = [
    path("analytics/dashboard/", views.dashboard, name="analytics-dashboard"),
    path("analytics/spending/", views.spending, name="analytics-spending"),
    path("analytics/frequency/", views.frequency, name="analytics-frequency"),
    path("analytics/nutrition/", views.nutrition, name="analytics-nutrition"),
    path("analytics/findings/", views.findings, name="analytics-findings"),
    path("analytics/data-quality/", views.data_quality, name="analytics-data-quality"),
]
