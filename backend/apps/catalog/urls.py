from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("vendors", views.VendorViewSet, basename="vendor")
router.register("foods", views.FoodViewSet, basename="food")
router.register("nutrition", views.NutritionViewSet, basename="nutrition")
router.register("meal-options", views.MealOptionViewSet, basename="meal-option")
urlpatterns = router.urls
