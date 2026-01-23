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
        except Exception as e:
            logger.exception("Skipping alert %s because building expr failed", alert.name)
            continue

        rules.append({
            "alert": alert.name,
            "expr": expr,
            "for": alert.duration,
            "labels": {
                "severity": alert.severity
            },
            "annotations": {
                "summary": f"Alert {alert.name} triggered"
            }
        })

    data = {
        "groups": [{
            "name": "django-managed-alerts",
            "rules": rules
        }]
    }

def generate_alert_rules():
    # ... construcción de data/yaml_text ...
    dirn = os.path.dirname(RULES_PATH) or "."
    os.makedirs(dirn, mode=0o755, exist_ok=True)
    try:
        logger.info("Writing %s with %d rules (in-place)", RULES_PATH, len(rules))
        with open(RULES_PATH, "w") as f:
            f.write(yaml_text)
        os.chmod(RULES_PATH, 0o644)
        logger.info("Wrote rules file %s", RULES_PATH)
    except Exception:
        logger.exception("Failed to write rules file %s", RULES_PATH)

    # Escritura atómica en RULES_PATH
    tmpname = None
    try:
        logger.info("Writing %s with %d rules", RULES_PATH, len(rules))
        with tempfile.NamedTemporaryFile('w', dir=dirn, delete=False) as tf:
            tf.write(yaml_text)
            tmpname = tf.name
        os.replace(tmpname, RULES_PATH)
        logger.info("Wrote rules file %s", RULES_PATH)

        # Permisos tipo 644 (rw- r-- r--)
        try:
            os.chmod(RULES_PATH, 0o644)
        except Exception:
            logger.exception("Failed to chmod 644 on %s", RULES_PATH)

        # Si necesitas propiedad específica dentro del contenedor, descomenta y ajusta:
        # import pwd, grp
        # uid = pwd.getpwnam("prometheus").pw_uid
        # gid = grp.getgrnam("prometheus").gr_gid
        # os.chown(RULES_PATH, uid, gid)

    except Exception:
        logger.exception("Failed to write rules file %s", RULES_PATH)
        # Limpieza del temporal si falló
        if tmpname and os.path.exists(tmpname):
            try:
                os.unlink(tmpname)
            except Exception:
                logger.warning("Could not remove temp file %s", tmpname)

    # Pide reload a Prometheus
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