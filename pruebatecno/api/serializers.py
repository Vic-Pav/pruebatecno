from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer):
    cpu_percent = serializers.FloatField()
    memory_percent = serializers.FloatField()
    load_avg_1m = serializers.FloatField()
    load_avg_5m = serializers.FloatField()
    load_avg_15m = serializers.FloatField()
    uptime_seconds = serializers.FloatField()
    hostname = serializers.CharField()
    timestamp = serializers.DateTimeField()