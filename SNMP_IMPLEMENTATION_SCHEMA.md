# Esquema de Implementación SNMP - Proyecto Pruebatecno

## 1. Visión General

Este documento describe la implementación lógica de SNMP (Simple Network Management Protocol) en el proyecto de monitoreo Pruebatecno, integrándose con la arquitectura existente de Prometheus, InfluxDB, Grafana y Alertmanager.

## 2. Arquitectura Actual del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PRESENTACIÓN                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │   Nginx Proxy    │    │     Grafana      │    │   Django Web  │ │
│  │   (Puerto 80)    │───▶│  (Puerto 3000)   │    │  (Puerto 8000)│ │
│  └──────────────────┘    └──────────────────┘    └───────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │                        │
                                    ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CAPA DE RECOLECCIÓN DE MÉTRICAS                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │   Prometheus     │    │    InfluxDB      │    │  System       │ │
│  │   (Puerto 9090)  │◀───│  (Puerto 8086)   │◀───│  Metrics      │ │
│  │                  │    │                  │    │  Exporter     │ │
│  └──────────────────┘    └──────────────────┘    │  (Puerto 9153)│ │
│           │                                       └───────────────┘ │
│           ▼                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │  Alertmanager    │    │  Redis Exporter  │    │  Redis Cache  │ │
│  │  (Puerto 9093)   │    │  (Puerto 9121)   │    │  (Puerto 6379)│ │
│  └──────────────────┘    └──────────────────┘    └───────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PERSISTENCIA                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    PostgreSQL Database                        │   │
│  │                      (Puerto 5432)                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Arquitectura Propuesta con SNMP

### 3.1 Componentes Nuevos

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA CON INTEGRACIÓN SNMP                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         DISPOSITIVOS DE RED                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Router     │  │   Switch     │  │   Firewall   │  ... más     │
│  │   (SNMP)     │  │   (SNMP)     │  │   (SNMP)     │  dispositivos│
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                       │
│         └─────────────────┼──────────────────┘                       │
│                           │ SNMP (UDP 161)                           │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      NUEVA CAPA DE SNMP POLLING                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    SNMP Exporter Container                    │   │
│  │                      (Puerto 9116)                            │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  • Lee configuración SNMP (snmp.yml)                   │  │   │
│  │  │  • Polling de dispositivos de red cada N segundos      │  │   │
│  │  │  • Mapea OIDs a métricas Prometheus                    │  │   │
│  │  │  • Expone endpoint /metrics para scraping             │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            │                                         │
│                            │ Prometheus Exposition Format            │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Prometheus Server                          │   │
│  │                      (Puerto 9090)                            │   │
│  │  • Scrape SNMP Exporter cada 15s                             │   │
│  │  • Almacena métricas de red                                  │   │
│  │  • Evalúa reglas de alertas                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESAMIENTO Y VISUALIZACIÓN                     │
│  ┌──────────────────┐    ┌──────────────────┐                       │
│  │  Grafana         │◀───│  InfluxDB        │                       │
│  │  • Dashboards    │    │  • Datos SNMP    │                       │
│  │    de red SNMP   │    │    opcionales    │                       │
│  └──────────────────┘    └──────────────────┘                       │
│                                                                       │
│  ┌──────────────────┐    ┌──────────────────┐                       │
│  │  Alertmanager    │◀───│  Django Web      │                       │
│  │  • Alertas de    │    │  • API gestión   │                       │
│  │    dispositivos  │    │    SNMP targets  │                       │
│  └──────────────────┘    └──────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. Flujo de Datos SNMP

### 4.1 Flujo de Recolección de Métricas

```
1. SNMP Polling (cada 15-60 segundos)
   ─────────────────────────────────────
   
   Dispositivo de Red (Router/Switch)
              │
              │ SNMP GET Request (OID)
              │ UDP Puerto 161
              ▼
      SNMP Exporter Container
              │
              │ Parse Response
              │ Map OID → Metric Name
              ▼
      Expone /metrics endpoint
      (Formato Prometheus)
      
      Ejemplo:
      snmp_interface_rx_bytes{
        interface="eth0",
        device="router-001"
      } 1234567890
      
              │
              │ HTTP Scrape (cada 15s)
              ▼
      Prometheus Server
              │
              │ PromQL Query
              ▼
      ┌──────────────┐
      │   Grafana    │ ← Visualización
      └──────────────┘
              │
              │ Opcional: Write Remote
              ▼
      ┌──────────────┐
      │   InfluxDB   │ ← Almacenamiento largo plazo
      └──────────────┘
```

### 4.2 Flujo de Alertas SNMP

```
Prometheus evalúa reglas
         │
         │ IF: snmp_interface_status != 1
         │     FOR: 5m
         ▼
  ┌──────────────┐
  │ Alert Firing │
  └──────────────┘
         │
         │ HTTP POST (JSON)
         ▼
  Alertmanager
         │
         ├─► Email notification
         ├─► Slack webhook
         └─► Django API webhook (opcional)
                   │
                   ▼
         Log en PostgreSQL
         (tabla: network_alerts)
```

## 5. Estructura de Configuración SNMP

### 5.1 Configuración del SNMP Exporter

**Archivo: `snmp-exporter/snmp.yml`**

```yaml
# Módulo para interfaces de red estándar
if_mib:
  walk:
    - 1.3.6.1.2.1.2.2.1.2   # ifDescr (nombres de interfaces)
    - 1.3.6.1.2.1.2.2.1.8   # ifOperStatus (estado de interfaces)
    - 1.3.6.1.2.1.2.2.1.10  # ifInOctets (bytes entrantes)
    - 1.3.6.1.2.1.2.2.1.16  # ifOutOctets (bytes salientes)
    - 1.3.6.1.2.1.2.2.1.14  # ifInErrors (errores entrantes)
    - 1.3.6.1.2.1.2.2.1.20  # ifOutErrors (errores salientes)
  
  metrics:
    - name: snmp_interface_status
      oid: 1.3.6.1.2.1.2.2.1.8
      type: gauge
      help: Interface operational status (1=up, 2=down)
      
    - name: snmp_interface_rx_bytes
      oid: 1.3.6.1.2.1.2.2.1.10
      type: counter
      help: Total bytes received on interface
      
    - name: snmp_interface_tx_bytes
      oid: 1.3.6.1.2.1.2.2.1.16
      type: counter
      help: Total bytes transmitted on interface

# Módulo para CPU/Memoria de dispositivos Cisco
cisco_system:
  walk:
    - 1.3.6.1.4.1.9.9.109.1.1.1  # CPU
    - 1.3.6.1.4.1.9.9.48.1.1.1   # Memoria
  
  metrics:
    - name: snmp_cisco_cpu_usage
      oid: 1.3.6.1.4.1.9.9.109.1.1.1.1.7
      type: gauge
      help: Cisco CPU usage percentage

# Módulo para dispositivos genéricos
generic:
  walk:
    - 1.3.6.1.2.1.1   # System MIB
    - 1.3.6.1.2.1.2   # Interfaces MIB
```

### 5.2 Configuración de Targets SNMP

**Archivo: `snmp-exporter/targets.json`**

```json
{
  "devices": [
    {
      "name": "router-core-01",
      "address": "192.168.1.1",
      "port": 161,
      "community": "public",
      "version": "2c",
      "module": "if_mib",
      "labels": {
        "site": "datacenter-1",
        "type": "router",
        "vendor": "cisco"
      }
    },
    {
      "name": "switch-access-01",
      "address": "192.168.1.10",
      "port": 161,
      "community": "public",
      "version": "2c",
      "module": "if_mib",
      "labels": {
        "site": "datacenter-1",
        "type": "switch",
        "vendor": "hp"
      }
    },
    {
      "name": "firewall-edge-01",
      "address": "192.168.1.254",
      "port": 161,
      "community": "public",
      "version": "2c",
      "module": "generic",
      "labels": {
        "site": "datacenter-1",
        "type": "firewall",
        "vendor": "fortinet"
      }
    }
  ]
}
```

### 5.3 Actualización de Prometheus

**Archivo: `prometheus/prometheus.yml`** (agregar al final)

```yaml
scrape_configs:
  # ... configuraciones existentes ...
  
  # Nueva configuración SNMP
  - job_name: 'snmp_devices'
    scrape_interval: 30s
    scrape_timeout: 10s
    static_configs:
      - targets:
        - router-core-01      # 192.168.1.1
        - switch-access-01    # 192.168.1.10
        - firewall-edge-01    # 192.168.1.254
    metrics_path: /snmp
    params:
      module: [if_mib]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: snmp_exporter:9116  # El servicio SNMP exporter
```

## 6. Docker Compose Integration

### 6.1 Servicio SNMP Exporter

**Agregar al archivo: `docker-compose.yml`**

```yaml
  snmp_exporter:
    image: prom/snmp-exporter:latest
    container_name: snmp_exporter
    ports:
      - "9116:9116"
    volumes:
      - ./snmp-exporter/snmp.yml:/etc/snmp_exporter/snmp.yml:ro
      - ./snmp-exporter/targets.json:/etc/snmp_exporter/targets.json:ro
    networks:
      - prueba
    command:
      - "--config.file=/etc/snmp_exporter/snmp.yml"
    restart: unless-stopped
```

## 7. Modelos Django para Gestión SNMP

### 7.1 Nuevos Modelos

**Archivo: `pruebatecno/metrics/models.py`** (agregar)

```python
class SNMPDevice(models.Model):
    """Dispositivo de red monitoreado via SNMP"""
    VENDOR_CHOICES = [
        ('cisco', 'Cisco'),
        ('hp', 'HP/Aruba'),
        ('juniper', 'Juniper'),
        ('fortinet', 'Fortinet'),
        ('other', 'Otro'),
    ]
    
    TYPE_CHOICES = [
        ('router', 'Router'),
        ('switch', 'Switch'),
        ('firewall', 'Firewall'),
        ('server', 'Servidor'),
        ('other', 'Otro'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    address = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=161)
    community = models.CharField(max_length=100, default='public')
    version = models.CharField(max_length=10, default='2c')
    snmp_module = models.CharField(max_length=50, default='if_mib')
    vendor = models.CharField(max_length=20, choices=VENDOR_CHOICES)
    device_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    site = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.address})"


class SNMPInterface(models.Model):
    """Interfaz de red detectada via SNMP"""
    device = models.ForeignKey(
        SNMPDevice, 
        related_name='interfaces',
        on_delete=models.CASCADE
    )
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)  # up, down, testing
    speed = models.BigIntegerField(null=True, blank=True)  # bits/sec
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['device', 'index']
        ordering = ['device', 'index']
    
    def __str__(self):
        return f"{self.device.name}:{self.name}"


class SNMPAlert(models.Model):
    """Alertas específicas de SNMP"""
    device = models.ForeignKey(SNMPDevice, on_delete=models.CASCADE)
    interface = models.ForeignKey(
        SNMPInterface,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    alert_type = models.CharField(max_length=50)  # interface_down, high_errors, etc
    severity = models.CharField(max_length=20)
    message = models.TextField()
    triggered_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-triggered_at']
    
    def __str__(self):
        return f"{self.device.name} - {self.alert_type}"
```

## 8. API REST para Gestión SNMP

### 8.1 Endpoints Propuestos

```
GET    /api/snmp/devices/              # Listar dispositivos SNMP
POST   /api/snmp/devices/              # Agregar dispositivo
GET    /api/snmp/devices/{id}/         # Detalle de dispositivo
PUT    /api/snmp/devices/{id}/         # Actualizar dispositivo
DELETE /api/snmp/devices/{id}/         # Eliminar dispositivo

GET    /api/snmp/devices/{id}/interfaces/    # Interfaces del dispositivo
POST   /api/snmp/devices/sync-config/        # Regenerar targets.json

GET    /api/snmp/alerts/               # Alertas SNMP
GET    /api/snmp/metrics/              # Métricas SNMP actuales
```

### 8.2 Serializers Django REST

**Archivo: `pruebatecno/api/serializers.py`** (agregar)

```python
from rest_framework import serializers
from metrics.models import SNMPDevice, SNMPInterface, SNMPAlert

class SNMPDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SNMPDevice
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class SNMPInterfaceSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = SNMPInterface
        fields = '__all__'

class SNMPAlertSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = SNMPAlert
        fields = '__all__'
```

## 9. Reglas de Alertas SNMP para Prometheus

**Archivo: `prometheus/snmp_alerts.yml`** (nuevo)

```yaml
groups:
  - name: snmp_network_alerts
    interval: 30s
    rules:
      # Alerta: Interfaz caída
      - alert: SNMPInterfaceDown
        expr: snmp_interface_status == 2
        for: 5m
        labels:
          severity: critical
          category: network
        annotations:
          summary: "Interfaz de red caída"
          description: "La interfaz {{ $labels.ifDescr }} en {{ $labels.instance }} está DOWN por más de 5 minutos"
      
      # Alerta: Alto tráfico de entrada
      - alert: SNMPHighInboundTraffic
        expr: rate(snmp_interface_rx_bytes[5m]) > 100000000  # >100MB/s
        for: 10m
        labels:
          severity: warning
          category: network
        annotations:
          summary: "Alto tráfico de entrada"
          description: "Interfaz {{ $labels.ifDescr }} en {{ $labels.instance }} recibiendo >100MB/s por 10min"
      
      # Alerta: Errores en interfaz
      - alert: SNMPInterfaceErrors
        expr: rate(snmp_interface_rx_errors[5m]) > 100
        for: 5m
        labels:
          severity: warning
          category: network
        annotations:
          summary: "Errores de interfaz detectados"
          description: "Interfaz {{ $labels.ifDescr }} en {{ $labels.instance }} tiene >100 errores/s"
      
      # Alerta: Dispositivo SNMP no responde
      - alert: SNMPDeviceDown
        expr: up{job="snmp_devices"} == 0
        for: 2m
        labels:
          severity: critical
          category: network
        annotations:
          summary: "Dispositivo SNMP no responde"
          description: "El dispositivo {{ $labels.instance }} no responde a consultas SNMP por más de 2 minutos"
      
      # Alerta: CPU alta en dispositivo Cisco
      - alert: SNMPCiscoCPUHigh
        expr: snmp_cisco_cpu_usage > 90
        for: 15m
        labels:
          severity: warning
          category: performance
        annotations:
          summary: "CPU alta en dispositivo Cisco"
          description: "CPU en {{ $labels.instance }} está al {{ $value }}% por 15 minutos"
```

## 10. Dashboard Grafana para SNMP

### 10.1 Estructura de Dashboard Propuesto

```
Dashboard: "Monitoreo de Red SNMP"
├── Row 1: Resumen General
│   ├── Panel: Total Dispositivos Monitoreados
│   ├── Panel: Interfaces Activas/Inactivas
│   └── Panel: Alertas Activas SNMP
│
├── Row 2: Estado de Interfaces
│   ├── Panel: Tabla de Interfaces con Estado
│   └── Panel: Mapa de Calor de Estados
│
├── Row 3: Tráfico de Red
│   ├── Panel: Tráfico Total (RX/TX) por Dispositivo
│   ├── Panel: Top 10 Interfaces por Tráfico
│   └── Panel: Gráfico de Ancho de Banda Histórico
│
├── Row 4: Errores y Problemas
│   ├── Panel: Errores por Interfaz
│   ├── Panel: Descartes de Paquetes
│   └── Panel: Colisiones Detectadas
│
└── Row 5: Performance de Dispositivos
    ├── Panel: CPU por Dispositivo (Cisco)
    ├── Panel: Memoria por Dispositivo
    └── Panel: Uptime de Dispositivos
```

### 10.2 Consultas PromQL de Ejemplo

```promql
# Total de interfaces UP
count(snmp_interface_status == 1)

# Total de interfaces DOWN
count(snmp_interface_status == 2)

# Tráfico de entrada por dispositivo (MB/s)
sum by (instance) (rate(snmp_interface_rx_bytes[5m])) / 1024 / 1024

# Tráfico de salida por dispositivo (MB/s)
sum by (instance) (rate(snmp_interface_tx_bytes[5m])) / 1024 / 1024

# Top 10 interfaces por tráfico
topk(10, rate(snmp_interface_rx_bytes[5m]) + rate(snmp_interface_tx_bytes[5m]))

# Porcentaje de errores en interfaces
(rate(snmp_interface_rx_errors[5m]) + rate(snmp_interface_tx_errors[5m])) / 
(rate(snmp_interface_rx_bytes[5m]) + rate(snmp_interface_tx_bytes[5m])) * 100
```

## 11. Tareas de Mantenimiento (Celery)

### 11.1 Tareas Programadas

**Archivo: `pruebatecno/metrics/tasks.py`** (agregar)

```python
from celery import shared_task
from .models import SNMPDevice, SNMPInterface
from .services.prometheus import query_prometheus
import json

@shared_task
def sync_snmp_interfaces():
    """
    Sincroniza las interfaces detectadas via SNMP con la base de datos
    Se ejecuta cada 5 minutos
    """
    # Consultar Prometheus por interfaces conocidas
    query = 'snmp_interface_status'
    results = query_prometheus(query)
    
    for result in results:
        device_ip = result['metric'].get('instance')
        if_index = result['metric'].get('ifIndex')
        if_name = result['metric'].get('ifDescr')
        status = result['value'][1]
        
        try:
            device = SNMPDevice.objects.get(address=device_ip)
            interface, created = SNMPInterface.objects.update_or_create(
                device=device,
                index=if_index,
                defaults={
                    'name': if_name,
                    'status': 'up' if status == '1' else 'down'
                }
            )
        except SNMPDevice.DoesNotExist:
            continue

@shared_task
def generate_snmp_targets_config():
    """
    Genera el archivo targets.json para el SNMP exporter
    basado en los dispositivos activos en la base de datos
    """
    devices = SNMPDevice.objects.filter(enabled=True)
    
    config = {
        "devices": [
            {
                "name": device.name,
                "address": device.address,
                "port": device.port,
                "community": device.community,
                "version": device.version,
                "module": device.snmp_module,
                "labels": {
                    "site": device.site,
                    "type": device.device_type,
                    "vendor": device.vendor,
                }
            }
            for device in devices
        ]
    }
    
    # Escribir archivo de configuración
    with open('/etc/snmp_exporter/targets.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    # Recargar SNMP exporter (señal)
    # En producción: hacer HTTP POST a SNMP exporter reload endpoint
    
    return f"Generated config for {devices.count()} devices"

@shared_task
def check_snmp_device_health():
    """
    Verifica el estado de salud de dispositivos SNMP
    consultando Prometheus
    """
    query = 'up{job="snmp_devices"}'
    results = query_prometheus(query)
    
    for result in results:
        instance = result['metric'].get('instance')
        is_up = result['value'][1] == '1'
        
        try:
            device = SNMPDevice.objects.get(name=instance)
            if not is_up:
                # Crear alerta
                SNMPAlert.objects.create(
                    device=device,
                    alert_type='device_unreachable',
                    severity='critical',
                    message=f'Dispositivo {device.name} no responde a SNMP'
                )
        except SNMPDevice.DoesNotExist:
            continue
```

## 12. Seguridad SNMP

### 12.1 Mejores Prácticas

1. **SNMPv3 con Autenticación**
   ```yaml
   # Preferir SNMPv3 sobre v1/v2c
   auth:
     username: snmp_user
     security_level: authPriv
     auth_protocol: SHA
     auth_password: strong_auth_password
     priv_protocol: AES
     priv_password: strong_priv_password
   ```

2. **Limitar acceso por ACL**
   - Configurar ACL en dispositivos para permitir solo IP del SNMP exporter
   - Usar comunidades de solo lectura (read-only)

3. **Variables de Entorno**
   ```bash
   # No hardcodear credenciales SNMP
   SNMP_COMMUNITY_STRING=${SNMP_COMMUNITY}
   SNMP_V3_USERNAME=${SNMP_USER}
   SNMP_V3_AUTH_PASS=${SNMP_AUTH_PASS}
   ```

4. **Red Segmentada**
   - Colocar SNMP exporter en red de gestión separada
   - Firewall entre red de gestión y red de producción

## 13. Monitoreo del Monitoreo

### 13.1 Métricas del SNMP Exporter

```promql
# Duración de scrapes SNMP
snmp_scrape_duration_seconds

# Éxito/Fallo de scrapes
snmp_scrape_success

# OIDs procesados por scrape
snmp_scrape_oids_count
```

### 13.2 Alertas Meta

```yaml
- alert: SNMPExporterDown
  expr: up{job="snmp_exporter"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "SNMP Exporter no responde"

- alert: SNMPScrapeSlow
  expr: snmp_scrape_duration_seconds > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Scrape SNMP muy lento"
```

## 14. Plan de Implementación

### Fase 1: Setup Básico (Semana 1)
- [ ] Agregar servicio SNMP exporter a docker-compose.yml
- [ ] Crear configuración inicial snmp.yml con módulo if_mib
- [ ] Configurar 2-3 dispositivos de prueba
- [ ] Actualizar prometheus.yml con scrape config SNMP
- [ ] Verificar métricas básicas en Prometheus

### Fase 2: Base de Datos y API (Semana 2)
- [ ] Crear migraciones para modelos SNMPDevice, SNMPInterface, SNMPAlert
- [ ] Implementar serializers Django REST
- [ ] Crear endpoints API CRUD para dispositivos SNMP
- [ ] Implementar generación dinámica de targets.json

### Fase 3: Alertas y Monitoreo (Semana 3)
- [ ] Crear reglas de alertas SNMP en Prometheus
- [ ] Integrar con Alertmanager
- [ ] Implementar webhooks a Django para log de alertas
- [ ] Crear tareas Celery para sincronización

### Fase 4: Visualización (Semana 4)
- [ ] Crear dashboard Grafana para SNMP
- [ ] Configurar paneles de estado de interfaces
- [ ] Configurar paneles de tráfico de red
- [ ] Configurar alertas visuales

### Fase 5: Producción (Semana 5)
- [ ] Migrar a SNMPv3 con autenticación
- [ ] Implementar respaldos de configuración
- [ ] Documentación de operación
- [ ] Capacitación del equipo

## 15. Métricas Clave de Éxito

- **Disponibilidad**: >99.9% uptime del sistema de monitoreo SNMP
- **Cobertura**: 100% de dispositivos críticos monitoreados
- **Latencia**: Scrapes SNMP <5 segundos
- **Alertas**: <1% falsos positivos
- **MTTR**: Mean Time To Resolution <15 minutos para alertas críticas

## 16. Diagrama de Flujo Completo

```
┌───────────────────────────────────────────────────────────────────────┐
│                          FLUJO COMPLETO SNMP                           │
└───────────────────────────────────────────────────────────────────────┘

Dispositivos de Red → SNMP Queries (UDP 161) → SNMP Exporter
                                                      │
                                                      │ Convierte a formato
                                                      │ Prometheus
                                                      ▼
                                            Expone /metrics endpoint
                                                      │
                      ┌───────────────────────────────┴──────────────┐
                      │                                              │
                      ▼                                              ▼
              Prometheus Server                                Django Web
              • Scrape cada 15s                                • Gestión de targets
              • Evalúa reglas                                  • Visualización logs
              • Almacena métricas                              • API REST CRUD
                      │                                              │
                      │                                              │
          ┌───────────┼─────────────┬────────────┐                  │
          │           │             │            │                  │
          ▼           ▼             ▼            ▼                  ▼
    Grafana    Alertmanager    InfluxDB     Django API       PostgreSQL DB
    • Dashboards  • Notifica   • Histórico  • Webhooks       • SNMPDevice
    • Visualiza   • Email      • Análisis   • Alertas        • SNMPInterface
                  • Slack                   • Reportes       • SNMPAlert

                              │
                              │ Feedback Loop
                              ▼
                     Usuario / Operador de Red
                     • Recibe alertas
                     • Visualiza dashboards
                     • Gestiona dispositivos
                     • Investiga incidentes
```

## 17. Conclusión

Esta implementación de SNMP se integra perfectamente con la arquitectura existente del proyecto Pruebatecno, aprovechando:

- **Prometheus** para recolección y alertas
- **InfluxDB** para almacenamiento histórico opcional
- **Grafana** para visualización
- **Django** para gestión y API
- **PostgreSQL** para persistencia
- **Docker Compose** para orquestación

El sistema es escalable, mantenible y sigue las mejores prácticas de la industria para monitoreo de redes mediante SNMP.
