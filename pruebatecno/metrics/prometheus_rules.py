import yaml
from metrics.models import PrometheusAlert

RULES_PATH = "/prometheus/alerts.yml"

def generate_rules():
    rules = []

    for alert in PrometheusAlert.objects.filter(enabled=True):
        rules.append({
            "alert": alert.name,
            "expr": f"{alert.metric} > {alert.threshold}",
            "for": alert.duration,
            "labels": {
                "severity": alert.severity
            },
            "annotations": {
                "summary": f"{alert.metric} above {alert.threshold}"
            }
        })

    data = {
        "groups": [{
            "name": "django-managed-alerts",
            "rules": rules
        }]
    }

    with open(RULES_PATH, "w") as f:
        yaml.dump(data, f)
