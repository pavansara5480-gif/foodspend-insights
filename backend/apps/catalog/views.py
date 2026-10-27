from django.db.models import Q
from rest_framework import viewsets
from rest_framework.response import Response

from apps.analytics.services import get_dataset
from apps.analytics.views import clean
from foodspend_core.analytics import preference_table

from .models import Food, MealOption, NutritionReference, Vendor
from .serializers import (FoodDetailSerializer, FoodSerializer, MealOptionSerializer, NutritionSerializer,
                          VendorSerializer)


class VendorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vendor.objects.all().order_by("vendor_id")
    serializer_class = VendorSerializer
    pagination_class = None


class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/foods/?category=&role=&search=  and  /api/foods/{food_id}/"""
    pagination_class = None

    def get_queryset(self):
        qs = Food.objects.select_related("vendor", "nutrition").prefetch_related("meal_options")
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        if p.get("role"):
            qs = qs.filter(role=p["role"])
        if p.get("search"):
            qs = qs.filter(Q(food_name__icontains=p["search"]) | Q(category__icontains=p["search"]))
        return qs

    def get_serializer_class(self):
        return FoodDetailSerializer if self.action == "retrieve" else FoodSerializer

    def retrieve(self, request, *args, **kwargs):
        food = self.get_object()
        data = FoodDetailSerializer(food).data
        t = preference_table(get_dataset())
        row = t[t["food_id"] == food.food_id]
        data["preference"] = clean(row.iloc[0].to_dict()) if len(row) else None
        return Response(data)


class NutritionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NutritionReference.objects.select_related("food").order_by("food_id")
    serializer_class = NutritionSerializer
    pagination_class = None


class MealOptionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/meal-options/?meal_type=lunch"""
    serializer_class = MealOptionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = MealOption.objects.select_related("food", "food__vendor").order_by("meal_option_id")
        if self.request.query_params.get("meal_type"):
            qs = qs.filter(meal_type=self.request.query_params["meal_type"])
        return qs
