from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer):
    cpu_percent = serializers.FloatField()
    memory_percent = serializers.FloatField()

class AlertRuleSerializer(serializers.Serializer):
    alert = serializers.CharField()
    expr = serializers.CharField()
    for_time = serializers.CharField(required=False, allow_blank=True, default = "", source ="for")
    labels = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    annotations = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    group = serializers.CharField(required=False, allow_blank=True, default="alerts")
