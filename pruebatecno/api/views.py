import socket, time
from datetime import datetime, timezone
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
        try:
            la1, la5, la15 = psutil.getloadavg()
        except (AttributeError, OSError):
            la1 = la5 = la15 = 0.0
        uptime = time.time() - psutil.boot_time()
        payload = {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "load_avg_1m": la1,
            "load_avg_5m": la5,
            "load_avg_15m": la15,
            "uptime_seconds": uptime,
            "hostname": socket.gethostname(),
            "timestamp": datetime.now(timezone.utc),
        }
        ser = SystemInfoSerializer(payload)
        return Response(ser.data, status=200)