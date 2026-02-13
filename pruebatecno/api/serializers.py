from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer):
    cpu_percent = serializers.FloatField()
    memory_percent = serializers.FloatField()
