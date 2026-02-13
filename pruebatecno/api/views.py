import psutil
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import SystemInfoSerializer

class SystemInfoView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent

        payload = {
            "cpu_percent": cpu,
            "memory_percent": mem,

        }
        ser = SystemInfoSerializer(payload)
        return Response(ser.data, status=200)