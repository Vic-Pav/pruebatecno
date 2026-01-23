from django.db import models

class MetricAlert(models.Model):
    METRIC_CHOICES = [
        ("Uso_CPU", "Uso de CPU"),
        ("Uso_RAM", "Uso de Memoria RAM"),
    ]
    
    metric = models.CharField(max_length=50, choices=METRIC_CHOICES)
    threshold = models.FloatField(help_text="Valor límite (%)")
    duration_seconds = models.PositiveIntegerField(
        help_text="Tiempo mínimo en segundos"
    )
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.metric} - {self.threshold}%"

class Alert(models.Model):
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    name = models.CharField(max_length=100, unique=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    duration = models.CharField(default="1m", max_length=10)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class AlertCondition(models.Model):
    OPERATOR_CHOICES = [
        (">", ">"),
        ("<", "<"),
        (">=", ">="),
        ("<=", "<="),
        ("==", "=="),
        ("!=", "!="),
    ]

    alert = models.ForeignKey(Alert, related_name="conditions", on_delete=models.CASCADE)
    metric = models.CharField(max_length=100)
    operator = models.CharField(max_length=2, choices=OPERATOR_CHOICES)
    threshold = models.FloatField()

    def __str__(self):
        return f"{self.metric} {self.operator} {self.threshold}"

class AlertLogic(models.Model):
    LOGIC_CHOICES = [
        ("AND", "AND"),
        ("OR", "OR"),
    ]

    alert = models.OneToOneField(Alert, related_name="alertlogic", on_delete=models.CASCADE)
    logic = models.CharField(max_length=3, choices=LOGIC_CHOICES, default="AND")

    def __str__(self):
        return f"{self.alert.name}: {self.logic}"


class AlertRuleVersion(models.Model):
    """Store generated Prometheus rules YAML for audit and rollback."""
    created_at = models.DateTimeField(auto_now_add=True)
    yaml = models.TextField()
    author = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AlertRuleVersion {self.created_at.isoformat()}"