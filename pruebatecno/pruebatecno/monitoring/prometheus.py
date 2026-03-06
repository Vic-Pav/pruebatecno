import os
import tempfile
import subprocess
import logging
from typing import Dict, Tuple, List, Optional, Any

import requests
import yaml
import hashlib

logger = logging.getLogger(__name__)

# Configuración centralizada
ALERTS_PATH = os.getenv("PROM_ALERTS_PATH") or os.getenv("PROM_RULES_PATH", "/prometheus/alerts.yml")
PROM_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://prometheus:9090")
PROM_ENABLE_RELOAD = os.getenv("PROM_ENABLE_RELOAD", "true").lower() == "true"
PROMTOOL_PATH = ("PROMTOOL_PATH", "promtool") 
ENABLE_PROOMTOOL_VALIDATION = os.getenv("ENABLE_PROMTOOL_VALIDATION", "false").lower()
DEFAULT_GROUP_NAME = "alerts"
RULES: List[Dict[str, Any]] = []
RULES_BY_ID: Dict[str,Dict[str,Any]] = {}
NEXT_RULE_ID: int = 1

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
    # Store in module-level cache and ensure each rule has an id and the RULES_BY_ID index
    global RULES
    RULES = rules
    try:
        ensure_rule_ids(RULES)
    except Exception:
        # ensure_rule_ids should be safe; on unexpected errors, log and continue
        logger.exception("ensure_rule_ids failed")
    return rules

def _make_rule_id(rule: Dict[str, Any]) -> str:
    # Generador simple: contador incremental (1,2,3...). Se reinicia
    # cada vez que se reconstruye el índice en `ensure_rule_ids`.
    global NEXT_RULE_ID
    val = str(NEXT_RULE_ID)
    NEXT_RULE_ID += 1
    return val

def ensure_rule_ids(rules_list: List[Dict[str, Any]]) -> None:
    # Preserve any existing numeric `id` found in the YAML and reuse it.
    # Then assign incremental ids only to rules that don't have an `id`.
    global NEXT_RULE_ID
    RULES_BY_ID.clear()

    max_id = 0
    # First pass: register existing ids
    for r in rules_list:
        existing = r.get('id')
        if existing is None:
            continue
        try:
            eid = int(existing)
            r['id'] = str(eid)
            RULES_BY_ID[r['id']] = r
            if eid > max_id:
                max_id = eid
        except Exception:
            # Non-numeric ids are preserved as strings but don't affect the counter
            r['id'] = str(existing)
            RULES_BY_ID[r['id']] = r

    # Start next id after the largest numeric existing id
    NEXT_RULE_ID = max_id + 1

    # Second pass: assign ids to rules that lack one
    for r in rules_list:
        if 'id' in r and r['id'] is not None:
            continue
        new_id = str(NEXT_RULE_ID)
        NEXT_RULE_ID += 1
        r['id'] = new_id
        RULES_BY_ID[new_id] = r

def get_rule_by_identifier(identifier: str, rules_list: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """
    Resuelve una regla desde YAML a partir de:
      1) Alert.id (si identifier es numérico) => busca en BD y mapea a Alert.name
      2) id generado legacy (RULES_BY_ID)
      3) nombre (rule['alert'] o rule['name'])
    """
    search_list = rules_list if rules_list is not None else globals().get("RULES", [])

    # 1) Si es numérico: interpretarlo como Alert.id y mapear a nombre
    #    (Sin agregar campos al YAML)
    try:
        int_id = int(str(identifier))
        try:
            from metrics.models import Alert
            db_alert = Alert.objects.filter(id=int_id).only("name").first()
            if db_alert:
                identifier = db_alert.name
        except Exception:
            # Si la BD no está disponible en este contexto, seguimos con fallback
            logger.exception("Failed to resolve Alert.id=%s to name", int_id)
    except (TypeError, ValueError):
        pass

    # 2) Legacy: lookup por id generado (si todavía existe)
    rule = RULES_BY_ID.get(str(identifier))
    if rule:
        return rule

    # 3) Fallback por nombre
    for r in search_list:
        if r.get("alert") == identifier or r.get("name") == identifier:
            return r
    return None
# ============================================================================
# FUNCIÓN DE ALTO NIVEL PARA DJANGO ADMIN
# ============================================================================

def generate_alert_rules(
    group_name: str = DEFAULT_GROUP_NAME,
    alert_id: Optional[int] = None,
) -> int:
    """
    Genera reglas desde modelos Django y las fusiona con el YAML existente.

    Si alert_id es None:
      - sincroniza TODAS las alertas enabled (comportamiento tipo "reconcile total")

    Si alert_id viene:
      - sincroniza SOLO esa alerta (update puntual)
      - si la alerta no existe o está disabled: elimina su regla (si existe) del YAML
    """
    logger.info(
        "generate_alert_rules called (group='%s', alert_id=%s)",
        group_name,
        alert_id,
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

    if alert_id is not None:
        # Solo una alerta
        qs = qs.filter(id=alert_id)

    # Si es total: solo enabled=True
    # Si es puntual: aquí conviene traerla aunque esté disabled para poder borrarla del YAML
    if alert_id is None:
        qs = qs.filter(enabled=True)

    alert = qs.first() if alert_id is not None else None

    # -----------------------------
    # 2) Si es puntual y NO existe: no podemos construir regla -> nada que actualizar
    #    (Opcional: podríamos borrar del YAML si supiéramos el nombre; pero no lo sabemos)
    # -----------------------------
    if alert_id is not None and alert is None:
        logger.warning("Alert id=%s not found; nothing to update", alert_id)
        return 0

    # -----------------------------
    # 3) Construir db_alerts (dict por nombre) solo para lo que corresponda
    # -----------------------------
    db_alerts: Dict[str, Dict] = {}

    if alert_id is None:
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
                "labels": {"severity": alert.severity, "managed_by": "django-admin", "alert_id": str(alert.id)},
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
                logger.exception("Cannot build expr for alert '%s' (id=%s)", alert.name, alert_id)
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
    if alert_id is None:
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
    # Rebuild index and return the persisted rule (with assigned id)
    try:
        rules = get_all_rules()
        found = get_rule_by_identifier(alert_name, rules)
        if found:
            return True, "created", found
    except Exception:
        logger.exception("Failed to rebuild rules index after create")
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
    # Rebuild index and return the persisted rule (with assigned id)
    try:
        rules = get_all_rules()
        found = get_rule_by_identifier(alert_name, rules)
        if found:
            return True, "updated", found
    except Exception:
        logger.exception("Failed to rebuild rules index after update")
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
    # Rebuild index and return the persisted rule (with assigned id)
    try:
        rules = get_all_rules()
        found = get_rule_by_identifier(rule.get("alert") or alert_name, rules)
        if found:
            return True, "patched", found
    except Exception:
        logger.exception("Failed to rebuild rules index after patch")
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
    # Rebuild index and attach id to the removed object if available
    try:
        rules = get_all_rules()
        found = get_rule_by_identifier(removed.get("alert"), rules)
        if found:
            removed_id = found.get("id")
            removed["id"] = removed_id
    except Exception:
        logger.exception("Failed to rebuild rules index after delete")

    return True, "deleted", removed