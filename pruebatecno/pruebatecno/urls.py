from django.contrib import admin
from django.urls import path, include
from metrics import views as metrics_views
from pruebatecno.celery.admin import celery_monitor_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/', include('api.urls')),
    path("metrics/", metrics_views.metrics_with_influx),
    path("metrics/influx/", metrics_views.metrics_influx_only),
    path("admin/celery-monitor/", celery_monitor_view, name="celery_monitor"),
]

