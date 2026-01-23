from django.contrib import admin
from django.urls import path, include
from django_prometheus import exports
from metrics import views as metrics_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tasks.urls")),
    path("metrics/", metrics_views.metrics_with_influx),
    path("metrics/influx/", metrics_views.metrics_influx_only),
    path("metrics/", include("django_prometheus.urls")),
]

