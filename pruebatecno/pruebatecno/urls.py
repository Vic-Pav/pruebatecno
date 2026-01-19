from django.contrib import admin
from django.urls import path, include
from django_prometheus import exports

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tasks.urls")),
    path("", include("django_prometheus.urls")),
    path("metrics/", exports.ExportToDjangoView),
]

