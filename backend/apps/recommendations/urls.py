from django.urls import path

from . import views

urlpatterns = [
    path("recommendations/next-meal/", views.next_meal, name="next-meal"),
    path("scenarios/simulate/", views.simulate_view, name="simulate"),
    path("scenarios/budget/", views.budget, name="budget"),
    path("scenarios/sensitivity/", views.sensitivity, name="sensitivity"),
]
