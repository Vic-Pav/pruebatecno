# Pruebatecno - Sistema de Monitoreo con SNMP

Sistema integral de monitoreo y métricas basado en Django, Prometheus, InfluxDB, Grafana y Alertmanager, con soporte para monitoreo de dispositivos de red via SNMP.

## 🏗️ Arquitectura del Sistema

El proyecto implementa una arquitectura de monitoreo completa con los siguientes componentes:

### Componentes Principales

- **Django Web Application**: Backend con API REST para gestión de alertas y configuración
- **PostgreSQL**: Base de datos principal para persistencia
- **Prometheus**: Recolección y almacenamiento de métricas time-series
- **InfluxDB**: Almacenamiento de métricas de largo plazo
- **Grafana**: Visualización y dashboards interactivos
- **Alertmanager**: Gestión y enrutamiento de alertas
- **Redis**: Cache y cola de mensajes
- **Nginx**: Reverse proxy y balanceador
- **SNMP Exporter**: Recolección de métricas de dispositivos de red _(Nuevo)_

### Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Capa de Presentación                      │
│  ┌────────────┐    ┌───────────┐    ┌──────────────┐       │
│  │   Nginx    │────│  Grafana  │    │  Django Web  │       │
│  │   :80      │    │   :3000   │    │    :8000     │       │
│  └────────────┘    └───────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                          │                     │
┌─────────────────────────────────────────────────────────────┐
│                 Capa de Métricas y Monitoreo                 │
│  ┌────────────┐    ┌───────────┐    ┌──────────────┐       │
│  │ Prometheus │◄───│  InfluxDB │◄───│   System     │       │
│  │   :9090    │    │   :8086   │    │   Metrics    │       │
│  └─────┬──────┘    └───────────┘    └──────────────┘       │
│        │                                                     │
│  ┌─────▼──────┐    ┌───────────┐    ┌──────────────┐       │
│  │   Alert    │    │   SNMP    │◄───│  Dispositivos│       │
│  │  Manager   │    │ Exporter  │    │  de Red      │       │
│  │   :9093    │    │   :9116   │    │              │       │
│  └────────────┘    └───────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                    Capa de Persistencia                      │
│  ┌────────────────────────────────────────────────────┐     │
│  │               PostgreSQL :5432                      │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Inicio Rápido

### Prerequisitos

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM mínimo
- Puertos disponibles: 80, 8086, 9090, 9116

### Instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/Vic-Pav/pruebatecno.git
cd pruebatecno
```

2. **Iniciar servicios**
```bash
docker-compose up -d
```

3. **Verificar servicios**
```bash
docker-compose ps
```

### Acceso a Interfaces

- **Aplicación Web**: http://localhost/
- **Grafana**: http://localhost/grafana (admin/admin)
- **Prometheus**: http://localhost/prometheus
- **InfluxDB**: http://localhost:8086
- **Alertmanager**: http://localhost/alertmanager

## 📡 Implementación SNMP

Este proyecto incluye una implementación completa de monitoreo SNMP para dispositivos de red.

### Documentación SNMP

- **[SNMP_IMPLEMENTATION_SCHEMA.md](./SNMP_IMPLEMENTATION_SCHEMA.md)** - Esquema completo de implementación SNMP con arquitectura detallada
- **[SNMP_QUICK_REFERENCE.md](./SNMP_QUICK_REFERENCE.md)** - Guía rápida de comandos y configuración SNMP
- **[SNMP_FLOW_DIAGRAMS.md](./SNMP_FLOW_DIAGRAMS.md)** - Diagramas de flujo de datos SNMP

### Configuración Rápida SNMP

1. **Crear directorio de configuración SNMP**
```bash
mkdir -p snmp-exporter
```

2. **Copiar configuración de ejemplo**
```bash
cp snmp-exporter-config-example.yml snmp-exporter/snmp.yml
```

3. **Agregar servicio SNMP al stack**
```bash
docker-compose -f docker-compose.yml -f docker-compose.snmp.yml up -d
```

4. **Actualizar configuración de Prometheus**
```bash
cp prometheus-with-snmp.yml prometheus/prometheus.yml
docker-compose restart prometheus
```

5. **Verificar funcionamiento**
```bash
# Test SNMP exporter
curl 'http://localhost:9116/snmp?target=192.168.1.1&module=if_mib'

# Ver targets en Prometheus
curl http://localhost:9090/prometheus/api/v1/targets | jq .
```

### Dispositivos Soportados via SNMP

- ✅ Routers Cisco (IOS, IOS-XE)
- ✅ Switches HP/Aruba
- ✅ Firewalls Fortinet
- ✅ Servidores Linux (Net-SNMP)
- ✅ Cualquier dispositivo con IF-MIB estándar

### Métricas SNMP Disponibles

- **Interfaces de Red**: Estado, tráfico RX/TX, errores, descartes
- **CPU**: Uso de CPU en dispositivos Cisco
- **Memoria**: Uso de memoria en dispositivos Cisco
- **Sistema**: Uptime, información del dispositivo
- **Temperatura**: Sensores térmicos (según dispositivo)

## 📊 Dashboards y Visualización

### Dashboards Preconfigurados

1. **Sistema**: Métricas de CPU, RAM, disco
2. **Aplicación**: Performance de Django, requests, errores
3. **Red SNMP**: Interfaces, tráfico, alertas de red _(Nuevo)_
4. **Redis**: Estado del cache, memoria, comandos

### Crear Dashboard SNMP Personalizado

1. Acceder a Grafana: http://localhost/grafana
2. Crear nuevo dashboard
3. Agregar panel con query PromQL:
```promql
# Tráfico de red por interfaz
sum by (instance, ifDescr) (rate(snmp_interface_rx_bytes[5m]))

# Estado de interfaces
snmp_interface_status

# Top 10 interfaces con más errores
topk(10, rate(snmp_interface_rx_errors[5m]))
```

## 🔔 Sistema de Alertas

### Tipos de Alertas

- **Sistema**: CPU alta, RAM alta, disco lleno
- **Aplicación**: Errores HTTP, latencia alta
- **Redis**: Memoria alta, conexiones rechazadas
- **Red SNMP**: Interfaces caídas, errores de red, tráfico alto _(Nuevo)_

### Configurar Alertas SNMP

Las reglas de alertas SNMP están en `prometheus/snmp_alerts.yml`:

```yaml
groups:
  - name: snmp_network_alerts
    rules:
      - alert: SNMPInterfaceDown
        expr: snmp_interface_status == 2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Interfaz de red caída"
          description: "{{ $labels.ifDescr }} en {{ $labels.instance }}"
```

### Notificaciones

Configurar en `alertmanager/alertmanager.yml`:
- Email
- Slack
- Webhook a Django
- PagerDuty
- Telegram

## 🔧 API REST

### Endpoints de Métricas

```bash
# Información del sistema
GET /api/system/info/

# Métricas de InfluxDB
GET /metrics/influx/

# Métricas solo de Django
GET /metrics/
```

### Endpoints SNMP _(Nuevo)_

```bash
# Listar dispositivos SNMP
GET /api/snmp/devices/

# Agregar dispositivo SNMP
POST /api/snmp/devices/
{
  "name": "router-01",
  "address": "192.168.1.1",
  "port": 161,
  "community": "public",
  "version": "2c",
  "vendor": "cisco",
  "device_type": "router"
}

# Ver interfaces de un dispositivo
GET /api/snmp/devices/{id}/interfaces/

# Ver alertas SNMP
GET /api/snmp/alerts/

# Sincronizar configuración SNMP
POST /api/snmp/devices/sync-config/
```

## 🛠️ Desarrollo

### Estructura del Proyecto

```
pruebatecno/
├── docker-compose.yml           # Orquestación principal
├── docker-compose.snmp.yml      # Extensión para SNMP
├── prometheus/
│   ├── prometheus.yml           # Config Prometheus
│   ├── alerts.yml               # Reglas de alertas
│   └── snmp_alerts.yml          # Alertas SNMP
├── snmp-exporter/
│   ├── snmp.yml                 # Módulos SNMP
│   └── targets.json             # Dispositivos a monitorear
├── grafana/
│   └── provisioning/            # Dashboards y datasources
├── alertmanager/
│   └── alertmanager.yml         # Config de notificaciones
├── pruebatecno/
│   ├── api/                     # API REST
│   ├── metrics/                 # App de métricas
│   ├── tasks/                   # App de tareas
│   └── pruebatecno/             # Settings Django
└── system-metrics/
    └── system_metrics_exporter.py  # Exporter de sistema
```

### Variables de Entorno

```bash
# Django
DATABASE_URL=postgres://admin:admin@postgres:5432/pruebadb
DEBUG=False
SECRET_KEY=your-secret-key

# InfluxDB
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=mytoken
INFLUX_ORG=prueba
INFLUX_BUCKET=metrics

# Redis
REDIS_URL=redis://redis:6379/0

# SNMP (opcional)
SNMP_COMMUNITY=your-community
SNMP_V3_USER=your-username
SNMP_V3_AUTH_PASS=your-auth-password
```

### Ejecutar Tests

```bash
# Tests de Django
docker-compose exec web python manage.py test

# Validar configuración Prometheus
docker-compose exec prometheus promtool check config /etc/prometheus/prometheus.yml

# Validar configuración SNMP Exporter
docker-compose exec snmp_exporter /bin/snmp_exporter --config.file=/etc/snmp_exporter/snmp.yml --dry-run
```

### Logs

```bash
# Todos los servicios
docker-compose logs -f

# Servicio específico
docker-compose logs -f snmp_exporter
docker-compose logs -f prometheus
docker-compose logs -f web
```

## 🔒 Seguridad

### Recomendaciones de Producción

1. **Cambiar credenciales por defecto**
   - PostgreSQL: admin/admin
   - Grafana: admin/admin
   - SNMP community: public

2. **Usar HTTPS**
   - Configurar certificados SSL en Nginx
   - Forzar redirección HTTP → HTTPS

3. **SNMPv3 con Autenticación**
   - Preferir SNMPv3 sobre v1/v2c
   - Usar autenticación SHA y cifrado AES

4. **Firewall**
   - Limitar acceso a puertos de gestión
   - Permitir solo IPs conocidas

5. **Secrets Management**
   - Usar Docker secrets
   - Variables de entorno en lugar de hardcode

### Actualizar Configuración

```bash
# Recargar Prometheus (sin reiniciar)
curl -X POST http://localhost:9090/prometheus/-/reload

# Recargar Alertmanager
docker-compose restart alertmanager

# Aplicar migraciones Django
docker-compose exec web python manage.py migrate

# Regenerar archivos estáticos
docker-compose exec web python manage.py collectstatic --no-input
```

## 📈 Monitoreo del Monitoreo

El sistema incluye métricas sobre sí mismo:

```promql
# Estado de todos los exporters
up{job=~"snmp_exporter|system_metrics|redis"}

# Duración de scrapes SNMP
snmp_scrape_duration_seconds

# Métricas de Prometheus
prometheus_tsdb_head_series
prometheus_tsdb_head_samples_appended_total
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📝 Licencia

Este proyecto está bajo licencia MIT. Ver archivo `LICENSE` para más detalles.

## 📞 Soporte

Para preguntas y soporte:
- Issues: https://github.com/Vic-Pav/pruebatecno/issues
- Documentación SNMP: Ver archivos `SNMP_*.md` en el repositorio
- Email: admin@example.com

## 🙏 Agradecimientos

- Prometheus Community
- Grafana Labs
- SNMP Exporter Contributors
- Django Team
- InfluxData

---

**Última actualización**: 2024-02-16
**Versión**: 1.0.0 con SNMP Support
