from django.contrib import admin
from django.urls import path, include
from api.views import SystemInfoView
from metrics import views as metrics_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/', include('api.urls')),
    path("api/system/", SystemInfoView.as_view(), name="system_info"),
    path("", include("tasks.urls")),
    path("metrics/", metrics_views.metrics_with_influx),
    path("metrics/influx/", metrics_views.metrics_influx_only),
]

