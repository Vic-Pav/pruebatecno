import os
import tempfile
import subprocess
import logging
from typing import Dict, Tuple, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# Configuración centralizada
ALERTS_PATH = os.getenv("PROM_ALERTS_PATH") or os.getenv("PROM_RULES_PATH", "/prometheus/alerts.yml")
PROM_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://prometheus:9090")
PROM_ENABLE_RELOAD = os.getenv("PROM_ENABLE_RELOAD", "true").lower() == "true"
PROMTOOL_PATH = ("PROMTOOL_PATH", "promtool") 
ENABLE_PROOMTOOL_VALIDATION = os.getenv("ENABLE_PROMTOOL_VALIDATION", "false").lower()
DEFAULT_GROUP_NAME = "alerts"

# ============================================================================
# FUNCIONES DE BAJO NIVEL (usadas por Admin y API REST)
# ============================================================================

def load_rules(path: str = ALERTS_PATH) -> Dict:
    """Carga alerts.yml completo con todos los grupos."""
    if not os.path.exists(path):
        return {"groups": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Error reading rules file %s: %s", path, e)
        return {"groups": []}
    
    groups = data.get("groups")
    if not isinstance(groups, list):
        groups = []
    return {"groups": groups}


def save_rules(data: Dict, path: str = ALERTS_PATH) -> None:
    """Escritura atómica de alerts.yml."""
    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, mode=0o755, exist_ok=True)
    
    fd, tmpfile = tempfile.mkstemp(prefix="alerts_", suffix=".yml", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        os.replace(tmpfile, path)
        os.chmod(path, 0o644)
    except Exception as e:
        logger.exception("Failed to save rules to %s", path)
        raise
    finally:
        try:
            os.remove(tmpfile)
        except Exception:
            pass


def validate_rules(path: str = ALERTS_PATH) -> Tuple[bool, str]:
    """Ejecuta 'promtool check rules' sobre alerts.yml."""
    try:
        proc = subprocess.run(
            [PROMTOOL_PATH, "check", "rules", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0, proc.stdout
    except FileNotFoundError:
        return False, "promtool no encontrado. Instálalo o define PROMTOOL_PATH."
    except subprocess.TimeoutExpired:
        return False, "Timeout ejecutando promtool."
    except Exception as e:
        return False, f"Error ejecutando promtool: {e}"


def reload_prometheus() -> Tuple[bool, str]:
    """Recarga Prometheus si está habilitado el endpoint."""
    if not PROM_ENABLE_RELOAD:
        return True, "reload deshabilitado (PROM_ENABLE_RELOAD=false)"
    try:
        r = requests.post(f"{PROM_BASE_URL}/-/reload", timeout=10)
        if r.status_code == 200:
            logger.info("Prometheus recargado exitosamente")
            return True, "Prometheus recargado"
        return False, f"Error recargando Prometheus: HTTP {r.status_code}"
    except Exception as e:
        logger.error("Error al recargar Prometheus: %s", e)
        return False, f"Error de conexión: {e}"


def find_rule(data: Dict, alert_name: str) -> Tuple[int, int]:
    """
    Busca una regla por nombre en todos los grupos.
    Devuelve (idx_grupo, idx_regla) o (-1, -1) si no existe.
    """
    for gi, group in enumerate(data.get("groups", [])):
        for ri, rule in enumerate(group.get("rules", [])):
            if rule.get("alert") == alert_name:
                return gi, ri
    return -1, -1


def ensure_group(data: Dict, group_name: str) -> int:
    """
    Garantiza que el grupo exista y devuelve su índice.
    Si no existe, lo crea.
    """
    groups = data.get("groups", [])
    for gi, g in enumerate(groups):
        if g.get("name") == group_name:
            return gi
    # Crear nuevo grupo
    groups.append({"name": group_name, "rules": []})
    data["groups"] = groups
    return len(groups) - 1


def get_all_rules(group_name: Optional[str] = None) -> List[Dict]:
    """
    Obtiene todas las reglas como lista plana.
    Si group_name se especifica, filtra solo ese grupo.
    """
    data = load_rules()
    rules = []
    for group in data.get("groups", []):
        if group_name and group.get("name") != group_name:
            continue
        for rule in group.get("rules", []):
            rule_copy = dict(rule)
            rule_copy["group"] = group.get("name")
            rules.append(rule_copy)
    return rules


# ============================================================================
# FUNCIÓN DE ALTO NIVEL PARA DJANGO ADMIN
# ============================================================================

def generate_alert_rules(
    group_name: str = DEFAULT_GROUP_NAME,
    alert_uuid: Optional[str] = None,
) -> int:
    """
    Genera reglas desde modelos Django y las fusiona con el YAML existente.

    Si alert_uuid es None:
      - sincroniza TODAS las alertas enabled (comportamiento tipo "reconcile total")

    Si alert_uuid viene:
      - sincroniza SOLO esa alerta (update puntual)
      - si la alerta no existe o está disabled: elimina su regla (si existe) del YAML
    """
    logger.info(
        "generate_alert_rules called (group='%s', alert_uuid=%s)",
        group_name,
        alert_uuid,
    )

    # Importaciones locales para evitar dependencias circulares
    try:
        from metrics.models import Alert
        from metrics.services.promql import build_promql
    except ImportError as e:
        logger.error("Cannot import Django models: %s", e)
        return 0

    data = load_rules()
    gi = ensure_group(data, group_name)
    target_group = data["groups"][gi]
    existing_rules = target_group.get("rules", [])
    if not isinstance(existing_rules, list):
        existing_rules = []

    # -----------------------------
    # 1) Selección de alertas objetivo
    # -----------------------------
    qs = Alert.objects.all()

    if alert_uuid is not None:
        # Solo una alerta
        qs = qs.filter(uuid=alert_uuid)

    # Si es total: solo enabled=True
    # Si es puntual: aquí conviene traerla aunque esté disabled para poder borrarla del YAML
    if alert_uuid is None:
        qs = qs.filter(enabled=True)

    alert = qs.first() if alert_uuid is not None else None

    # -----------------------------
    # 2) Si es puntual y NO existe: no podemos construir regla -> nada que actualizar
    #    (Opcional: podríamos borrar del YAML si supiéramos el nombre; pero no lo sabemos)
    # -----------------------------
    if alert_uuid is not None and alert is None:
        logger.warning("Alert uuid=%s not found; nothing to update", alert_uuid)
        return 0

    # -----------------------------
    # 3) Construir db_alerts (dict por nombre) solo para lo que corresponda
    # -----------------------------
    db_alerts: Dict[str, Dict] = {}

    if alert_uuid is None:
        # modo total (todas enabled)
        for a in qs:
            try:
                expr = build_promql(a)
            except Exception:
                logger.exception("Skipping alert '%s' because building expr failed", a.name)
                continue

            db_alerts[a.name] = {
                "alert": a.name,
                "expr": expr,
                "for": a.duration,
                "labels": {"severity": a.severity, "managed_by": "django-admin"},
                "annotations": {"summary": f"Alert {a.name} triggered"},
            }
    else:
        # modo puntual (una alerta)
        # Si está disabled, significa "quitarla del YAML"
        if not alert.enabled:
            logger.info("Alert '%s' is disabled; will remove rule from YAML if present", alert.name)
            db_alerts = {}
        else:
            try:
                expr = build_promql(alert)
            except Exception:
                logger.exception("Cannot build expr for alert '%s' (uuid=%s)", alert.name, alert_uuid)
                return 0

            db_alerts[alert.name] = {
                "alert": alert.name,
                "expr": expr,
                "for": alert.duration,
                "labels": {"severity": alert.severity, "managed_by": "django-admin"},
                "annotations": {"summary": f"Alert {alert.name} triggered"},
            }

    # -----------------------------
    # 4) Merge:
    #   - modo total: mismo merge que tenías (DB manda, API se preserva)
    #   - modo puntual: actualizar/agregar/quitar solo esa alerta por nombre
    # -----------------------------
    if alert_uuid is None:
        merged_rules = []
        db_alert_names = set(db_alerts.keys())
        processed_from_yaml = set()

        for rule in existing_rules:
            alert_name = rule.get("alert")
            if not alert_name:
                merged_rules.append(rule)
                continue

            if alert_name in db_alert_names:
                merged_rules.append(db_alerts[alert_name])
                processed_from_yaml.add(alert_name)
            else:
                merged_rules.append(rule)

        for alert_name, rule in db_alerts.items():
            if alert_name not in processed_from_yaml:
                merged_rules.append(rule)

    else:
        # puntual
        target_name = alert.name  # existe, porque validamos alert != None
        merged_rules = []

        for rule in existing_rules:
            if rule.get("alert") == target_name:
                # saltamos la regla vieja (la vamos a reemplazar o eliminar)
                continue
            merged_rules.append(rule)

        # si la alerta está enabled (db_alerts tiene la regla), la agregamos
        if target_name in db_alerts:
            merged_rules.append(db_alerts[target_name])

    target_group["rules"] = merged_rules
    data["groups"][gi] = target_group

    # Guardar YAML
    save_rules(data)

    # Recargar Prometheus
    ok, msg = reload_prometheus()
    if not ok:
        logger.warning("Prometheus reload failed after updating rules: %s", msg)

    return len(merged_rules)


# ============================================================================
# FUNCIONES DE CONVENIENCIA PARA API REST
# ============================================================================

def create_rule(alert_name: str, expr: str, duration: str = "", 
                labels: Optional[Dict] = None, annotations: Optional[Dict] = None,
                group_name: str = DEFAULT_GROUP_NAME) -> Tuple[bool, str, Optional[Dict]]:
    """
    Crea una nueva regla de alerta.
    
    Returns:
        (success, message, rule_dict)
    """
    data = load_rules()
    
    # Verificar duplicados
    if find_rule(data, alert_name)[0] >= 0:
        return False, "Alert rule already exists", None
    
    # Añadir la regla al grupo
    gi = ensure_group(data, group_name)
    rule = {
        "alert": alert_name,
        "expr": expr,
        "for": duration,
        "labels": labels or {},
        "annotations": annotations or {},
    }
    
    # Marcar origen
    if "managed_by" not in rule["labels"]:
        rule["labels"]["managed_by"] = "api"
    
    data["groups"][gi]["rules"].append(rule)
    
    # Guardar
    try:
        save_rules(data)
    except Exception as e:
        return False, f"Failed to save: {e}", None
    
    # Validar
    #ok, output = validate_rules()
    #if not ok:
    #    return False, f"Validation failed: {output}", None
    
    # Recargar
    reload_prometheus()
    
    rule["group"] = group_name
    return True, "created", rule


def update_rule(alert_name: str, expr: str, duration: str = "",
                labels: Optional[Dict] = None, annotations: Optional[Dict] = None,
                new_group: Optional[str] = None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Actualiza una regla existente (PUT completo).
    
    Returns:
        (success, message, rule_dict)
    """
    data = load_rules()
    gi, ri = find_rule(data, alert_name)
    if gi < 0:
        return False, "Alert rule not found", None
    
    current_group = data["groups"][gi]["name"]
    target_group = new_group or current_group
    
    rule = {
        "alert": alert_name,
        "expr": expr,
        "for": duration,
        "labels": labels or {},
        "annotations": annotations or {},
    }
    
    # Si cambia de grupo, mover
    if target_group != current_group:
        data["groups"][gi]["rules"].pop(ri)
        gi2 = ensure_group(data, target_group)
        data["groups"][gi2]["rules"].append(rule)
    else:
        data["groups"][gi]["rules"][ri] = rule
    
    try:
        save_rules(data)
    except Exception as e:
        return False, f"Failed to save: {e}", None
    
    #ok, output = validate_rules()
    #if not ok:
    #    return False, f"Validation failed: {output}", None
    
    reload_prometheus()
    
    rule["group"] = target_group
    return True, "updated", rule


def patch_rule(alert_name: str, updates: Dict) -> Tuple[bool, str, Optional[Dict]]:
    """
    Actualiza parcialmente una regla (PATCH).
    
    Args:
        alert_name: Nombre de la alerta
        updates: Dict con campos a actualizar (expr, for, labels, annotations, group)
    
    Returns:
        (success, message, rule_dict)
    """
    data = load_rules()
    gi, ri = find_rule(data, alert_name)
    if gi < 0:
        return False, "Alert rule not found", None
    
    current_group = data["groups"][gi]["name"]
    rule = dict(data["groups"][gi]["rules"][ri])
    
    # Aplicar actualizaciones parciales
    if "expr" in updates:
        rule["expr"] = updates["expr"]
    if "for" in updates:
        rule["for"] = updates["for"]
    if "labels" in updates:
        rule["labels"] = updates["labels"]
    if "annotations" in updates:
        rule["annotations"] = updates["annotations"]
    
    # Mover de grupo si se especifica
    new_group = updates.get("group", current_group)
    if new_group != current_group:
        data["groups"][gi]["rules"].pop(ri)
        gi2 = ensure_group(data, new_group)
        data["groups"][gi2]["rules"].append(rule)
        current_group = new_group
    else:
        data["groups"][gi]["rules"][ri] = rule
    
    try:
        save_rules(data)
    except Exception as e:
        return False, f"Failed to save: {e}", None
    
    #ok, output = validate_rules()
    #if not ok:
    #    return False, f"Validation failed: {output}", None
    
    reload_prometheus()
    
    rule["group"] = current_group
    return True, "patched", rule


def delete_rule(alert_name: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Elimina una regla de alerta.
    
    Returns:
        (success, message, deleted_rule_dict)
    """
    data = load_rules()
    gi, ri = find_rule(data, alert_name)
    if gi < 0:
        return False, "Alert rule not found", None
    
    removed = data["groups"][gi]["rules"].pop(ri)
    removed["group"] = data["groups"][gi]["name"]
    
    try:
        save_rules(data)
    except Exception as e:
        return False, f"Failed to save: {e}", None
    
    #ok, output = validate_rules()
    #if not ok:
    #    return False, f"Validation failed: {output}", None
    
    reload_prometheus()
    
    return True, "deleted", removed