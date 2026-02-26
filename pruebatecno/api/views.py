from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action

from .serializers import SystemInfoSerializer, AlertRuleSerializer
from pruebatecno.core.system_info import build_system_payload

# Importar desde el módulo unificado
from pruebatecno.monitoring.prometheus import (
    load_rules,
    get_all_rules,
    find_rule,
    create_rule,
    update_rule,
    patch_rule,
    delete_rule,
    validate_rules,
    reload_prometheus,
    ALERTS_PATH,
)


class SystemInfoView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        payload = build_system_payload()
        ser = SystemInfoSerializer(payload)
        return Response(ser.data, status=200)


class AlertRuleViewSet(viewsets.ViewSet):
    authentication_classes = []
    permission_classes = []

    def list(self, request):
        """Lista todas las alertas (Admin + API)."""
        items = get_all_rules()
        return Response(items, status=200)

    def retrieve(self, request, pk=None):
        """Obtiene una alerta específica por nombre."""
        data = load_rules()
        gi, ri = find_rule(data, pk)
        if gi < 0:
            return Response({"detail": "Alert rule not found"}, status=404)
        rule = dict(data["groups"][gi]["rules"][ri])
        rule["group"] = data["groups"][gi]["name"]
        return Response(rule, status=200)

    def create(self, request):
        """Crea una nueva alerta."""
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        
        item = ser.validated_data
        success, msg, rule = create_rule(
            alert_name=item["alert"],
            expr=item["expr"],
            duration=item.get("for", ""),
            labels=item.get("labels"),
            annotations=item.get("annotations"),
            group_name=item.get("group", "alerts")
        )
        
        if not success:
            status_code = 409 if "already exists" in msg else 400
            return Response({"detail": msg}, status=status_code)
        
        return Response({
            "detail": msg,
            "reload": "triggered",
            "rule": rule
        }, status=201)

    def update(self, request, pk=None):
        """Actualiza completamente una alerta (PUT)."""
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        
        item = ser.validated_data
        success, msg, rule = update_rule(
            alert_name=pk,
            expr=item["expr"],
            duration=item.get("for", ""),
            labels=item.get("labels"),
            annotations=item.get("annotations"),
            new_group=item.get("group")
        )
        
        if not success:
            status_code = 404 if "not found" in msg else 400
            return Response({"detail": msg}, status=status_code)
        
        return Response({
            "detail": msg,
            "reload": "triggered",
            "rule": rule
        }, status=200)

    def partial_update(self, request, pk=None):
        """Actualiza parcialmente una alerta (PATCH)."""
        success, msg, rule = patch_rule(pk, request.data)
        
        if not success:
            status_code = 404 if "not found" in msg else 400
            return Response({"detail": msg}, status=status_code)
        
        return Response({
            "detail": msg,
            "reload": "triggered",
            "rule": rule
        }, status=200)

    def destroy(self, request, pk=None):
        """Elimina una alerta."""
        success, msg, rule = delete_rule(pk)
        
        if not success:
            status_code = 404 if "not found" in msg else 400
            return Response({"detail": msg}, status=status_code)
        
        return Response({
            "detail": msg,
            "reload": "triggered",
            "rule": rule
        }, status=200)

    @action(detail=False, methods=["post"])
    def validate(self, request):
        """Valida el archivo alerts.yml con promtool."""
        ok, output = validate_rules()
        return Response({
            "ok": ok,
            "output": output
        }, status=200 if ok else 400)

    @action(detail=False, methods=["post"])
    def reload(self, request):
        """Recarga Prometheus manualmente."""
        ok, msg = reload_prometheus()
        return Response({
            "ok": ok,
            "message": msg
        }, status=200 if ok else 500)