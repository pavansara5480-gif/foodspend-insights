import math

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.analytics.params import get_choice, get_int, period
from apps.analytics.services import get_dataset
from apps.analytics.views import clean
from foodspend_core.analytics import filter_period, item_nutrition
from foodspend_core.constants import NUTRIENTS

from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer

MEAL_CHOICES = {"breakfast", "lunch", "snack", "dinner", "not_applicable"}
RECORD_CHOICES = {r[0] for r in Order.RECORD_TYPES}


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    """GET /api/orders/?start=&end=&meal_type=&record_type=&category=&food=  (paginated)
    GET /api/orders/{order_id}/     POST /api/orders/ (prices computed server-side)"""
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related("vendor").prefetch_related("items__food")
        start, end = period(self.request)
        meal = get_choice(self.request, "meal_type", MEAL_CHOICES)
        rec = get_choice(self.request, "record_type", RECORD_CHOICES)
        p = self.request.query_params
        if start:
            qs = qs.filter(order_date__gte=start)
        if end:
            qs = qs.filter(order_date__lte=end)
        if meal:
            qs = qs.filter(meal_type=meal)
        if rec:
            qs = qs.filter(record_type=rec)
        if p.get("category"):
            qs = qs.filter(items__food__category=p["category"]).distinct()
        if p.get("food"):
            qs = qs.filter(Q(items__food_id=p["food"]) | Q(items__food__food_name__icontains=p["food"])).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = s.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def history(request):
    """Item-level food history with estimated nutrients (same formula as the analysis).

    Filters: start, end, meal_type, record_type, category, consumption, search; page, page_size.
    """
    start, end = period(request)
    ds = filter_period(get_dataset(), start, end)
    df = item_nutrition(ds).merge(ds.orders[["order_id", "order_datetime", "vendor_id"]], on="order_id")
    df = df.merge(ds.vendors[["vendor_id", "vendor_name"]], on="vendor_id", how="left")
    p = request.query_params
    meal = get_choice(request, "meal_type", MEAL_CHOICES)
    rec = get_choice(request, "record_type", RECORD_CHOICES)
    cons = get_choice(request, "consumption", {"consumed", "partially_consumed", "not_consumed", "unknown"})
    if meal:
        df = df[df["meal_type"] == meal]
    if rec:
        df = df[df["record_type"] == rec]
    if cons:
        df = df[df["consumption_status"] == cons]
    if p.get("category"):
        df = df[df["category"] == p["category"]]
    if p.get("search"):
        df = df[df["food_name"].str.contains(p["search"], case=False, regex=False)]
    df = df.sort_values(["order_datetime", "order_item_id"], ascending=[False, True])
    page_size = get_int(request, "page_size", 25, 1, 200)
    total = len(df)
    pages = max(1, math.ceil(total / page_size))
    page = min(get_int(request, "page", 1, 1, 100000), pages)
    rows = df.iloc[(page - 1) * page_size: page * page_size]
    cols = ["order_item_id", "order_id", "order_datetime", "meal_type", "record_type", "vendor_name", "food_id",
            "food_name", "category", "quantity", "serving_size", "serving_unit", "unit_price_inr", "line_total_inr",
            "consumption_status", "portion_consumed"] + [f"purchased_{n}" for n in NUTRIENTS] + \
           [f"consumed_{n}" for n in NUTRIENTS]
    categories = sorted(get_dataset().foods["category"].unique())
    return Response(clean({"count": total, "page": page, "pages": pages, "page_size": page_size,
                           "categories": categories, "results": rows[cols],
                           "note": "'Purchased' nutrients describe what was bought; 'consumed' applies the recorded "
                                   "portion and is empty when consumption is unknown."}))
