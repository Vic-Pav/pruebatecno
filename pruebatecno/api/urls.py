from django.urls import path
from .views import metrics_influx_only

urlpatterns = [
    path('system/', metrics_influx_only),
]
