import socket
import time
from datetime import datetime, timezone

import psutil
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SystemInfoSerializer

class SystemInfoView(APIView):
    """
    Devuelve parámetros del sistema en JSON:
    - cpu_percent, memory_percent, 
    - load_avg (1m, 5m, 15m)
    - uptime_seconds
    - hostname
    - timestamp (UTC)
    """
    authentication_classes = []  # en dev; en prod, usa autenticación si procede
    permission_classes = []      # en dev; en prod, aplica permisos (IsAuthenticated)

    def get(self, request):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent


        uptime = time.time() - psutil.boot_time()
        payload = {
            "cpu_percent": cpu,
            "memory_percent": mem,
        }
        # Valida y serializa con DRF
        ser = SystemInfoSerializer(payload)
        return Response(ser.data, status=200)