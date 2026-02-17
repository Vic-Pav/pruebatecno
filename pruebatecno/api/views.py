from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import SystemInfoSerializer
from pruebatecno.core.system_info import build_system_payload

class SystemInfoView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        payload = build_system_payload()
        ser = SystemInfoSerializer(payload)
        return Response(ser.data, status=200)