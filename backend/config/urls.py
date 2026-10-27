from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.catalog.urls")),
    path("api/", include("apps.orders.urls")),
    path("api/", include("apps.preferences.urls")),
    path("api/", include("apps.health.urls")),
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.recommendations.urls")),
]
