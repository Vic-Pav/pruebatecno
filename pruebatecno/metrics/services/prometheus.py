import yaml
import tempfile
from metrics.models import Alert, AlertRuleVersion
from metrics.services.promql import build_promql
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

RULES_PATH = "/prometheus/alerts.yml"

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

    # Ensure target directory exists
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    yaml_text = yaml.dump(data)
    # Persist YAML in database for audit/rollback
    try:
        AlertRuleVersion.objects.create(yaml=yaml_text)
        logger.info('Saved AlertRuleVersion to DB (length=%d)', len(yaml_text))
    except Exception:
        logger.exception('Failed to save AlertRuleVersion to DB')

    # Write atomically to RULES_PATH
    try:
        logger.info("Writing %s with %d rules", RULES_PATH, len(rules))
        dirn = os.path.dirname(RULES_PATH) or "."
        with tempfile.NamedTemporaryFile('w', dir=dirn, delete=False) as tf:
            tf.write(yaml_text)
            tmpname = tf.name
        os.replace(tmpname, RULES_PATH)
        logger.info("Wrote rules file %s", RULES_PATH)
    except Exception:
        logger.exception("Failed to write rules file %s", RULES_PATH)
    # Ask Prometheus to reload its configuration so new rules are picked up.
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
