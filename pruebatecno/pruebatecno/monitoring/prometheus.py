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
PROMTOOL_PATH = os.getenv("PROMTOOL_PATH", "promtool")
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

def generate_alert_rules(group_name: str = DEFAULT_GROUP_NAME):
    """
    Genera reglas desde modelos Django y las fusiona con el YAML existente.
    
    Comportamiento:
    - Lee el YAML completo
    - Actualiza/añade alertas que están en la DB de Django
    - Preserva alertas que NO están en la DB (creadas por API u otros medios)
    - Escribe el YAML completo
    - Recarga Prometheus
    
    Args:
        group_name: Nombre del grupo donde se gestionarán las alertas del Admin
    """
    logger.info("generate_alert_rules called (merge mode, group='%s')", group_name)
    
    # Importaciones locales para evitar dependencias circulares
    try:
        from metrics.models import Alert
        from metrics.services.promql import build_promql
    except ImportError as e:
        logger.error("Cannot import Django models: %s", e)
        return
    
    # 1. Leer el YAML actual
    data = load_rules()
    
    # 2. Buscar o crear el grupo objetivo
    gi = ensure_group(data, group_name)
    target_group = data["groups"][gi]
    existing_rules = target_group.get("rules", [])
    if not isinstance(existing_rules, list):
        existing_rules = []
    
    # 3. Generar reglas desde la base de datos de Django
    db_alerts = {}  # {alert_name: rule_dict}
    for alert in Alert.objects.filter(enabled=True):
        try:
            expr = build_promql(alert)
        except Exception:
            logger.exception("Skipping alert '%s' because building expr failed", alert.name)
            continue
        
        db_alerts[alert.name] = {
            "alert": alert.name,
            "expr": expr,
            "for": alert.duration,
            "labels": {"severity": alert.severity, "managed_by": "django-admin"},
            "annotations": {"summary": f"Alert {alert.name} triggered"},
        }
    
    # 4. Merge inteligente: actualizar/añadir desde DB, preservar las demás
    merged_rules = []
    db_alert_names = set(db_alerts.keys())
    processed_from_yaml = set()
    
    # Procesar reglas existentes en el YAML
    for rule in existing_rules:
        alert_name = rule.get("alert")
        if not alert_name:
            # Regla sin nombre, preservarla
            merged_rules.append(rule)
            continue
        
        if alert_name in db_alert_names:
            # Esta alerta está en la DB: usar versión de la DB (source of truth)
            merged_rules.append(db_alerts[alert_name])
            processed_from_yaml.add(alert_name)
            logger.debug("Updated alert '%s' from DB", alert_name)
        else:
            # Esta alerta NO está en la DB: preservarla (creada por API)
            merged_rules.append(rule)
            logger.debug("Preserved alert '%s' (not in DB)", alert_name)
    
    # Añadir alertas de la DB que no estaban en el YAML
    for alert_name, rule in db_alerts.items():
        if alert_name not in processed_from_yaml:
            merged_rules.append(rule)
            logger.debug("Added new alert '%s' from DB", alert_name)
    
    # 5. Actualizar el grupo con las reglas fusionadas
    target_group["rules"] = merged_rules
    data["groups"][gi] = target_group
    
    # 6. Guardar el archivo
    try:
        save_rules(data)
        logger.info("Wrote %s: %d groups, %d rules in '%s' group (%d from DB, %d preserved)",
                    ALERTS_PATH, len(data["groups"]), len(merged_rules), 
                    group_name, len(db_alerts), len(merged_rules) - len(db_alerts))
    except Exception:
        logger.exception("Failed to write rules file")
        return
    
    # 7. Validar (opcional, puede ser costoso)
    # ok, output = validate_rules()
    # if not ok:
    #     logger.warning("Rules validation failed: %s", output)
    
    # 8. Recargar Prometheus
    reload_prometheus()


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
    ok, output = validate_rules()
    if not ok:
        return False, f"Validation failed: {output}", None
    
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
    
    ok, output = validate_rules()
    if not ok:
        return False, f"Validation failed: {output}", None
    
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
    
    ok, output = validate_rules()
    if not ok:
        return False, f"Validation failed: {output}", None
    
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
    
    ok, output = validate_rules()
    if not ok:
        return False, f"Validation failed: {output}", None
    
    reload_prometheus()
    
    return True, "deleted", removed