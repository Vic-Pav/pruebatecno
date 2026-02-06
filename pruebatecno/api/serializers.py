from rest_framework import serializers

class SystemInfoSerializer(serializers.Serializer): 
    cpu_usage = serializers.FloatField()
    ram_usage = serializers.FloatField()