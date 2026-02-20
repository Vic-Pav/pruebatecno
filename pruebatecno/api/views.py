from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action   

from .serializers import SystemInfoSerializer, AlertRuleSerializer
from pruebatecno.core.system_info import build_system_payload
from pruebatecno.monitoring.prometheus import (
    load_rules, save_rules, validate_rules, reload_prometheus,
    find_rule, ensure_group, DEFAULT_ALERTS_PATH
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
        data = load_rules()
        items = []
        for g in data.get("groups", []):
            for r in g.get("rules", []):
                item = dict(r)
                item["group"] = g.get("name", "alerts")
                items.append(item)
        return Response(items, status=200)
    
    def retrieve(self, request, pk=None):
        data = load_rules()
        gi, ri = find_rule(data, pk)
        if gi < 0:
            return Response({"detail": "Alert rule not found"}, status=404)
        rule = dict(data["groups"][gi]["rules"][ri])
        rule["group"] = data["groups"][gi]["name"]
        return Response(rule, status=200)

    def create(self, request):
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        item = ser.validated_data
        data = load_rules()

        if find_rule(data, item["alert"])[0] >= 0:
            return Response({"detail": "Alert rule already exists"}, status=409)

        gi = ensure_group(data, item.get("group", "alerts"))
        rule = {
            "alert": item["alert"],
            "expr": item["expr"],
            "for": item.get("for", ""),
            "labels": item.get("labels", {}) or {},
            "annotations": item.get("annotations", {}) or {},
        }
        data["groups"][gi]["rules"].append(rule)

        save_rules(data, DEFAULT_ALERTS_PATH)
        ok, out = validate_rules(DEFAULT_ALERTS_PATH)
        if not ok:
            return Response({"detail": "promtool validation failed", "output": out}, status=400)

        ok2, msg = reload_prometheus()
        rule["group"] = data["groups"][gi]["name"]
        return Response({"detail": "created", "reload": msg, "rule": rule}, status=201)

    def update(self, request, pk=None):
        ser = AlertRuleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        item = ser.validated_data
        data = load_rules()
        gi, ri = find_rule(data, pk)
        if gi < 0:
            return Response({"detail": "Alert rule not found"}, status=404)

        new_group = item.get("group", data["groups"][gi]["name"])
        rule = {
            "alert": item["alert"],
            "expr": item["expr"],
            "for": item.get("for", ""),
            "labels": item.get("labels", {}) or {},
            "annotations": item.get("annotations", {}) or {},
        }
        if new_group != data["groups"][gi]["name"]:
            data["groups"][gi]["rules"].pop(ri)
            gi2 = ensure_group(data, new_group)
            data["groups"][gi2]["rules"].append(rule)
        else:
            data["groups"][gi]["rules"][ri] = rule

        save_rules(data, DEFAULT_ALERTS_PATH)
        ok, out = validate_rules(DEFAULT_ALERTS_PATH)
        if not ok:
            return Response({"detail": "promtool validation failed", "output": out}, status=400)
        ok2, msg = reload_prometheus()
        rule["group"] = new_group
        return Response({"detail": "updated", "reload": msg, "rule": rule}, status=200)

    def partial_update(self, request, pk=None):
        data = load_rules()
        gi, ri = find_rule(data, pk)
        if gi < 0:
            return Response({"detail": "Alert rule not found"}, status=404)

        current = dict(data["groups"][gi]["rules"][ri])
        group_name = data["groups"][gi]["name"]

        for key in ["alert", "expr", "for", "labels", "annotations"]:
            if key in request.data:
                current[key] = request.data[key]

        new_group = request.data.get("group", group_name)
        if new_group != group_name:
            data["groups"][gi]["rules"].pop(ri)
            gi2 = ensure_group(data, new_group)
            data["groups"][gi2]["rules"].append(current)
            group_name = new_group
        else:
            data["groups"][gi]["rules"][ri] = current

        save_rules(data, DEFAULT_ALERTS_PATH)
        ok, out = validate_rules(DEFAULT_ALERTS_PATH)
        if not ok:
            return Response({"detail": "promtool validation failed", "output": out}, status=400)
        ok2, msg = reload_prometheus()
        current["group"] = group_name
        return Response({"detail": "patched", "reload": msg, "rule": current}, status=200)

    def destroy(self, request, pk=None):
        data = load_rules()
        gi, ri = find_rule(data, pk)
        if gi < 0:
            return Response({"detail": "Alert rule not found"}, status=404)
        removed = data["groups"][gi]["rules"].pop(ri)
        save_rules(data, DEFAULT_ALERTS_PATH)
        ok, out = validate_rules(DEFAULT_ALERTS_PATH)
        if not ok:
            return Response({"detail": "promtool validation failed", "output": out}, status=400)
        ok2, msg = reload_prometheus()
        removed["group"] = data["groups"][gi]["name"]
        return Response({"detail": "deleted", "reload": msg, "rule": removed}, status=200)

    @action(detail=False, methods=["post"])
    def validate(self, request):
        ok, out = validate_rules(DEFAULT_ALERTS_PATH)
        return Response({"ok": ok, "output": out}, status=200 if ok else 400)

    @action(detail=False, methods=["post"])
    def reload(self, request):
        ok, msg = reload_prometheus()
        return Response({"ok": ok, "message": msg}, status=200 if ok else 500)