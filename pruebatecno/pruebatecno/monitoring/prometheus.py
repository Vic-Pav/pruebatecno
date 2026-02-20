import os
import tempfile
import subprocess
from typing import Dict

import yaml
import requests

DEFAULT_ALERTS_PATH = os.getenv("PROMETHEUS_ALERTS_PATH", "/etc/prometheus/alerts.yml")
PROM_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://prometheus:9090")
PROM_ENABLE_RELOAD = os.getenv("PROMETHEUS_ENABLE_RELOAD", "true").lower() == "true"
PROMTOOL_PATH = os.getenv("PROMTOOL_PATH", "promtool")

def load_rules(path: str = DEFAULT_ALERTS_PATH) -> Dict:
    """Cargar las reglas de alerta desde un archivo .yml"""
    
    if not os.path.exists(path):
        return {"groups": [{"name": "alerts", "rules": []}]}  # Devuelve un grupo vacío si el archivo no existe
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    groups = data.get("groups") or [{"name": "alerts", "rules": []}]
    return {"groups": groups}

def save_rules(data: Dict, path: str = DEFAULT_ALERTS_PATH) -> None:
    """escrtura de las reglas de alerta en un archivo .yml, creando el directorio si no existe"""
    dirpatch = os.path.dirname(path) or "."
    os.makedirs(dirpatch, exist_ok=True)
    fd, tmpfile = tempfile.mkstemp(prefix="alerts_", suffix=".yml", dir=dirpatch)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        os.replace(tmpfile, path)
    finally:
        try:
            os.remove(tmpfile)
        except Exception:
            pass  

def validate_rules(path: str = DEFAULT_ALERTS_PATH) -> tuple[bool, str]:
    """Validar las reglas de alerta usando promtool"""
    try:
        proc = subprocess.run(
            [PROMTOOL_PATH, "check", "rules", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0, proc.stdout
    except FileNotFoundError:
        return False, f"Error: promtool not found at {PROMTOOL_PATH}"
    except subprocess.TimeoutExpired:
        return False, "Error: promtool validation timed out"
    
def reload_prometheus() -> tuple[bool, str]:
    """Solicitar a Prometheus que recargue su configuración de reglas"""
    if not PROM_ENABLE_RELOAD:
        return True, "Recarga prometheus deshabilitada (PROM_ENABLE_RELOAD=false)"
    try:
        r = requests.post(f"{PROM_BASE_URL}/-/reload", timeout=10)
        if r.status_code == 200:
            return True, "Prometheus recargado exitosamente"
        return False, f"Error al recargar Prometheus: status code: HTTP{r.status_code}"
    except Exception as e:
        return False, f"Error al recargar Prometheus: {e}"

def find_rule(data: Dict, alert_name: str) -> tuple[int, int]:
    """Buscar una regla de alerta por su nombre en la estructura de reglas"""
    for g1, group in enumerate(data.get("groups", [])):
        for r1, rule in enumerate(group.get("rules", [])):
            if rule.get("alert") == alert_name:
                return g1, r1
    return -1, -1

def ensure_group(data: Dict, group_name: str) -> int:
    """Asegurar que exista un grupo de reglas con el nombre dado, y devolver su índice"""
    groups = data.get("groups", [])
    for g1, g in enumerate(groups):
        if g.get("name") == group_name:
            return g1
    groups.append({"name": group_name, "rules": []})
    data.setdefault("groups", []).append({"name": group_name, "rules": []})
    return len(data["groups"]) - 1