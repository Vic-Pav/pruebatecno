from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer):
    cpu_percent = serializers.FloatField()
    memory_percent = serializers.FloatField()


class AlertConditionInputSerializer(serializers.Serializer):
    metric = serializers.CharField()
    operator = serializers.ChoiceField(choices=[">", "<", ">=", "<=", "==", "!="])
    threshold = serializers.FloatField()


class AlertRuleSerializer(serializers.Serializer):
    """
    Payload para crear/actualizar alertas desde Postman.

    Este serializer ahora permite:
      - Definir la alerta en BD (severity, duration, enabled)
      - Definir lógica AND/OR
      - Definir conditions[] para construir el expr vía build_promql(alert)
      - group/labels/annotations para la regla en YAML

    NOTA:
      - expr se ignora para la generación DB-managed (se recalcula desde BD).
    """
    alert = serializers.CharField()  # Alert.name

    # Campos BD (Alert)
    severity = serializers.ChoiceField(choices=["info", "warning", "critical"], required=False)
    duration = serializers.CharField(required=False, allow_blank=True, source="for")
    enabled = serializers.BooleanField(required=False)

    # BD (AlertLogic)
    logic = serializers.ChoiceField(choices=["AND", "OR"], required=False)

    # BD (AlertCondition)
    conditions = AlertConditionInputSerializer(many=True, required=False)

    # YAML extras
    labels = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    annotations = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    group = serializers.CharField(required=False, allow_blank=True, default="alerts")

    def validate_duration(self, value):
        # Si está vacío, devolver None en lugar de cadena vacía
        if value == "" or value is None:
            return None
        return value