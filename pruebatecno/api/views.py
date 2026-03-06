from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action
from django.db import transaction

from .serializers import SystemInfoSerializer, AlertRuleSerializer
from pruebatecno.core.system_info import build_system_payload

# Importar desde el módulo unificado
from pruebatecno.monitoring.prometheus import (
    load_rules,
    get_all_rules,
    find_rule,
    get_rule_by_identifier,
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
        """Obtiene una alerta específica por id o nombre."""
        # aseguramos que la lista/índice de reglas esté cargado en este proceso
        # (get_all_rules construye RULES y RULES_BY_ID)
        get_all_rules()
        # intentamos buscar por id (rápido) o por nombre (compatibilidad)
        rule = get_rule_by_identifier(pk)
        if not rule:
            return Response({"detail": "Alert rule not found"}, status=404)
        return Response(rule, status=200)

    def create(self, request):
        """
        Crea una nueva alerta en BD (Alert + Conditions + Logic) y sincroniza YAML.
        Retorna `alert_id` (Alert.id) para que el cliente use IDs estables.
        """
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        item = ser.validated_data

        from metrics.models import Alert, AlertCondition, AlertLogic
        from pruebatecno.monitoring.prometheus import generate_alert_rules, get_all_rules, get_rule_by_identifier

        alert_name = item["alert"]
        severity = item.get("severity") or item.get("labels", {}).get("severity") or "warning"
        duration = item.get("for") or "1m"
        enabled = item.get("enabled")
        if enabled is None:
            enabled = True

        logic = item.get("logic")  # "AND"/"OR" o None
        conditions = item.get("conditions", [])

        # Validación mínima: si vamos a generar expr desde BD, necesitamos conditions
        if not conditions:
            return Response(
                {"detail": "conditions es requerido para crear alertas DB-managed"},
                status=400,
            )

        with transaction.atomic():
            alert_obj, created = Alert.objects.get_or_create(
                name=alert_name,
                defaults={
                    "severity": severity,
                    "duration": duration,
                    "enabled": enabled,
                },
            )
            if not created:
                # Si ya existe, actualizamos campos base si vienen
                alert_obj.severity = severity
                alert_obj.duration = duration
                alert_obj.enabled = enabled
                alert_obj.save(update_fields=["severity", "duration", "enabled"])

            # Reemplazar conditions completamente (simple y determinista)
            AlertCondition.objects.filter(alert=alert_obj).delete()
            AlertCondition.objects.bulk_create(
                [
                    AlertCondition(
                        alert=alert_obj,
                        metric=c["metric"],
                        operator=c["operator"],
                        threshold=c["threshold"],
                    )
                    for c in conditions
                ]
            )

            # Lógica (one-to-one)
            if logic:
                AlertLogic.objects.update_or_create(
                    alert=alert_obj,
                    defaults={"logic": logic},
                )

        # Sincronizar YAML solo para esta alerta por id (estable)
        rules_count = generate_alert_rules(alert_id=alert_obj.id)

        # Devolver la regla desde YAML
        rules = get_all_rules()
        rule = get_rule_by_identifier(alert_obj.name, rules)

        return Response(
            {
                "detail": "created" if created else "updated",
                "alert_id": alert_obj.id,
                "rules_count": rules_count,
                "rule": rule,
            },
            status=201 if created else 200,
    )
    def update(self, request, pk=None):
        """
        PUT: actualiza completamente una alerta en BD por Alert.id (pk numérico) o nombre,
        luego regenera YAML.
        """
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        item = ser.validated_data

        from metrics.models import Alert, AlertCondition, AlertLogic
        from pruebatecno.monitoring.prometheus import generate_alert_rules, get_all_rules, get_rule_by_identifier

        # Resolver Alert desde pk:
        alert_obj = None
        try:
            alert_obj = Alert.objects.filter(id=int(pk)).first()
        except Exception:
            alert_obj = Alert.objects.filter(name=str(pk)).first()

        if not alert_obj:
            return Response({"detail": "Alert not found in DB"}, status=404)

        severity = item.get("severity") or item.get("labels", {}).get("severity") or alert_obj.severity
        duration = item.get("for") or alert_obj.duration
        enabled = item.get("enabled")
        if enabled is None:
            enabled = alert_obj.enabled

        logic = item.get("logic")
        conditions = item.get("conditions", [])

        if not conditions:
            return Response({"detail": "conditions es requerido en PUT"}, status=400)

        with transaction.atomic():
            alert_obj.severity = severity
            alert_obj.duration = duration
            alert_obj.enabled = enabled
            alert_obj.save(update_fields=["severity", "duration", "enabled"])

            AlertCondition.objects.filter(alert=alert_obj).delete()
            AlertCondition.objects.bulk_create(
                [
                    AlertCondition(
                        alert=alert_obj,
                        metric=c["metric"],
                        operator=c["operator"],
                        threshold=c["threshold"],
                    )
                    for c in conditions
                ]
            )

            if logic:
                AlertLogic.objects.update_or_create(alert=alert_obj, defaults={"logic": logic})

        rules_count = generate_alert_rules(alert_id=alert_obj.id)

        rules = get_all_rules()
        rule = get_rule_by_identifier(alert_obj.name, rules)

        return Response(
            {
                "detail": "updated",
                "alert_id": alert_obj.id,
                "rules_count": rules_count,
                "rule": rule,
            },
            status=200,
        )

    def partial_update(self, request, pk=None):
        """
        PATCH: actualiza parcialmente una alerta en BD y luego regenera YAML.
        """
        ser = AlertRuleSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        item = ser.validated_data

        from metrics.models import Alert, AlertCondition, AlertLogic
        from pruebatecno.monitoring.prometheus import generate_alert_rules, get_all_rules, get_rule_by_identifier

        alert_obj = None
        try:
            alert_obj = Alert.objects.filter(id=int(pk)).first()
        except Exception:
            alert_obj = Alert.objects.filter(name=str(pk)).first()

        if not alert_obj:
            return Response({"detail": "Alert not found in DB"}, status=404)

        with transaction.atomic():
            if "severity" in item or ("labels" in item and "severity" in item.get("labels", {})):
                alert_obj.severity = item.get("severity") or item.get("labels", {}).get("severity") or alert_obj.severity

            if "for" in item:
                alert_obj.duration = item.get("for") or alert_obj.duration

            if "enabled" in item:
                alert_obj.enabled = item["enabled"]

            alert_obj.save()

            if "conditions" in item:
                conditions = item.get("conditions") or []
                if not conditions:
                    return Response({"detail": "conditions no puede ser vacío si se envía en PATCH"}, status=400)

                AlertCondition.objects.filter(alert=alert_obj).delete()
                AlertCondition.objects.bulk_create(
                    [
                        AlertCondition(
                            alert=alert_obj,
                            metric=c["metric"],
                            operator=c["operator"],
                            threshold=c["threshold"],
                        )
                        for c in conditions
                    ]
                )

            if "logic" in item and item.get("logic"):
                AlertLogic.objects.update_or_create(alert=alert_obj, defaults={"logic": item["logic"]})

        rules_count = generate_alert_rules(alert_id=alert_obj.id)

        rules = get_all_rules()
        rule = get_rule_by_identifier(alert_obj.name, rules)

        return Response(
            {
                "detail": "patched",
                "alert_id": alert_obj.id,
                "rules_count": rules_count,
                "rule": rule,
            },
            status=200,
        )

    def destroy(self, request, pk=None):
        """
        Elimina una alerta DB-managed:
        - borra Alert (y cascada: conditions / logic)
        - borra la regla del YAML por nombre
        Mantiene compatibilidad si pk es nombre.
        """
        from metrics.models import Alert
        from pruebatecno.monitoring.prometheus import (
            get_all_rules,
            get_rule_by_identifier,
            delete_rule,
        )

        # 1) Resolver Alert en BD por id o nombre
        alert_obj = None
        alert_name = None

        try:
            alert_obj = Alert.objects.filter(id=int(pk)).only("id", "name").first()
        except Exception:
            alert_obj = Alert.objects.filter(name=str(pk)).only("id", "name").first()

        if alert_obj:
            alert_name = alert_obj.name
        else:
            # Si no existe en BD, intentamos resolver al menos en YAML (compatibilidad)
            get_all_rules()
            found = get_rule_by_identifier(str(pk))
            if not found:
                return Response({"detail": "Alert not found"}, status=404)
            alert_name = found.get("alert")

        # 2) Borrar en BD (si existe)
        if alert_obj:
            alert_obj.delete()

        # 3) Borrar en YAML por nombre
        success, msg, rule = delete_rule(alert_name)

        if not success:
            status_code = 404 if "not found" in msg else 400
            return Response({"detail": msg}, status=status_code)

        return Response(
            {
                "detail": "deleted",
                "deleted_alert": alert_name,
                "rule": rule,
            },
            status=200,
        )

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