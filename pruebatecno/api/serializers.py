from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer):
    cpu_percent = serializers.FloatField()
    memory_percent = serializers.FloatField()

class AlertRuleSerializer(serializers.Serializer):
    alert = serializers.CharField()
    expr = serializers.CharField()
    {
    "detail": "Validation failed: promtool no encontrado. Instálalo o define PROMTOOL_PATH."
}
    # ← FIX: No usar default="", dejar que sea None
    duration = serializers.CharField(
        required=False, 
        allow_blank=True,
        source="for"
    )
    
    labels = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    annotations = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    group = serializers.CharField(required=False, allow_blank=True, default="alerts")
    
    def validate_duration(self, value):
        """Si está vacío, devolver None en lugar de cadena vacía"""
        if value == "" or value is None:
            return None
        return value