import yaml
import tempfile
from metrics.models import Alert, AlertRuleVersion
from metrics.services.promql import build_promql
import os
import logging
import urllib.request
import urllib.error
import stat

logger = logging.getLogger(__name__)
RULES_PATH = os.environ.get("PROM_RULES_PATH", "/prometheus/alerts.yml")

def generate_alert_rules():
    logger.info("generate_alert_rules called")
    rules = []
    for alert in Alert.objects.filter(enabled=True):
        try:
            expr = build_promql(alert)
        except Exception:
            logger.exception("Skipping alert %s because building expr failed", alert.name)
            continue
        rules.append({
            "alert": alert.name,
            "expr": expr,
            "for": alert.duration,
            "labels": {"severity": alert.severity},
            "annotations": {"summary": f"Alert {alert.name} triggered"},
        })

    data = {"groups": [{"name": "django-managed-alerts", "rules": rules}]}
    yaml_text = yaml.dump(data)

    dirn = os.path.dirname(RULES_PATH) or "."
    os.makedirs(dirn, mode=0o755, exist_ok=True)

    # Escritura in-place (evita cambiar inode)
    try:
        logger.info("Writing %s with %d rules (in-place)", RULES_PATH, len(rules))
        with open(RULES_PATH, "w") as f:
            f.write(yaml_text)
        os.chmod(RULES_PATH, 0o644)  # rw- r-- r--
        logger.info("Wrote rules file %s", RULES_PATH)
    except Exception:
        logger.exception("Failed to write rules file %s", RULES_PATH)

    # Reload Prometheus
    try:
        reload_url = "http://prometheus:9090/-/reload"
        req = urllib.request.Request(reload_url, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.getcode() != 200:
                logger.error("Prometheus reload returned status %s", resp.getcode())
            else:
                logger.info("Requested Prometheus reload successfully")
    except urllib.error.URLError:
        logger.exception("Failed to request Prometheus reload at http://prometheus:9090/-/reload")
    except Exception:
        logger.exception("Unexpected error when requesting Prometheus reload")