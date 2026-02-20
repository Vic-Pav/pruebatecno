from django.urls import path, include
from rest_framework import DefaultRouter
from .views import SystemInfoView, AlertRuleViewSet

router = DefaultRouter()
router.register(r'alerts', AlertRuleViewSet, basename='alert-rule')

urlpatterns = [
    path('system/', SystemInfoView.as_view(), name='system_info'),
    path('', include(router.urls)),
]
