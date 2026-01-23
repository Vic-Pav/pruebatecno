from django.contrib import admin
from .models import MetricAlert, Alert, AlertCondition, AlertLogic

class AlertConditionInline(admin.TabularInline):
    model = AlertCondition
    extra = 1
    fields = ("metric", "operator", "threshold")
    show_change_link = True

class AlertLogicInline(admin.StackedInline):
    model = AlertLogic
    can_delete = False
    max_num = 1

@admin.action(description="Habilitar alertas seleccionadas")
def enable_alerts(modeladmin, request, queryset):
    queryset.update(enabled=True)

@admin.action(description="Deshabilitar alertas seleccionadas")
def disable_alerts(modeladmin, request, queryset):
    queryset.update(enabled=False)

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("name", "severity", "enabled", "duration")
    list_filter = ("severity", "enabled")
    search_fields = ("name",)
    ordering = ("-severity", "name")
    inlines = [AlertLogicInline, AlertConditionInline]
    actions = [enable_alerts, disable_alerts]
    list_editable = ("enabled",)

@admin.register(MetricAlert)
class MetricAlertAdmin(admin.ModelAdmin):
    list_display = ("metric", "threshold", "duration_seconds", "enabled")
    list_filter = ("metric", "enabled")
    search_fields = ("metric",)

@admin.register(AlertCondition)
class AlertConditionAdmin(admin.ModelAdmin):
    list_display = ("alert", "metric", "operator", "threshold")
    list_filter = ("operator",)
    search_fields = ("metric", "alert__name")
    raw_id_fields = ("alert",)

@admin.register(AlertLogic)
class AlertLogicAdmin(admin.ModelAdmin):
    list_display = ("alert", "logic")
    raw_id_fields = ("alert",)