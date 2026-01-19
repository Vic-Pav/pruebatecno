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
        return f"{self.metric} > {self.threshold}%"

class PrometheusAlert(models.Model):
    name = models.CharField(max_length=100, unique=True)
    metric = models.CharField(max_length=100)
    threshold = models.FloatField()
    duration = models.CharField(
        max_length=10,
        help_text="Ej: 30s, 1m, 5m"
    )
    severity = models.CharField(
        max_length=20,
        default="warning"
    )
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name
