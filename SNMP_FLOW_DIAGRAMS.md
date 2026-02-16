# Diagramas de Flujo - Implementación SNMP

Este documento contiene diagramas ASCII que muestran el flujo de datos en la implementación SNMP.

## 1. Flujo General del Sistema Completo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE DISPOSITIVOS DE RED                          │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Router    │  │   Switch    │  │  Firewall   │  │   Server    │       │
│  │ 192.168.1.1 │  │192.168.1.10 │  │192.168.1.254│  │192.168.2.50 │       │
│  │  SNMP v2c   │  │  SNMP v2c   │  │  SNMP v3    │  │  Net-SNMP   │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │                │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          │ SNMP Query     │ SNMP Query     │ SNMP Query     │ SNMP Query
          │ GET OID        │ GET OID        │ GET OID        │ GET OID
          │ UDP:161        │ UDP:161        │ UDP:161        │ UDP:161
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                                    │
                                    ▼
          ┌─────────────────────────────────────────────────────────┐
          │           SNMP Exporter Container                       │
          │              (prom/snmp-exporter)                       │
          │                                                         │
          │  1. Recibe solicitud HTTP de Prometheus                │
          │     GET /snmp?target=192.168.1.1&module=if_mib         │
          │                                                         │
          │  2. Consulta dispositivo via SNMP                      │
          │     snmpget -v2c -c public 192.168.1.1 [OIDs]          │
          │                                                         │
          │  3. Parsea respuestas SNMP                             │
          │     OID → Nombre de métrica                            │
          │     Valores → Valores numéricos                        │
          │                                                         │
          │  4. Formatea a exposición Prometheus                   │
          │     snmp_interface_rx_bytes{...} 1234567               │
          │                                                         │
          │  Expone: http://snmp_exporter:9116/snmp                │
          └─────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP GET (cada 30s)
                                    ▼
          ┌─────────────────────────────────────────────────────────┐
          │           Prometheus Server                             │
          │                                                         │
          │  • Scrape targets cada N segundos                      │
          │  • Almacena métricas en TSDB local                     │
          │  • Evalúa reglas de alertas                            │
          │  • Expone API PromQL                                   │
          │                                                         │
          │  Expone: http://prometheus:9090                        │
          └─────────────────────────────────────────────────────────┘
                        │                       │
                        │                       │
            ┌───────────┴─────┐       ┌─────────┴──────────┐
            │                 │       │                    │
            ▼                 ▼       ▼                    ▼
    ┌─────────────┐   ┌─────────────────┐        ┌──────────────┐
    │   Grafana   │   │  Alertmanager   │        │  Django Web  │
    │             │   │                 │        │              │
    │ Dashboards  │   │  Notificaciones │        │  API REST    │
    │ Visualiza   │   │  • Email        │        │  Gestión     │
    │ Métricas    │   │  • Slack        │        │  Dispositivos│
    └─────────────┘   │  • Webhook      │        └──────────────┘
                      └────────┬────────┘                │
                               │                         │
                               │ Webhook                 │
                               └─────────────────────────┘
                                         │
                                         ▼
                              ┌────────────────────┐
                              │   PostgreSQL DB    │
                              │                    │
                              │  • SNMPDevice      │
                              │  • SNMPInterface   │
                              │  • SNMPAlert       │
                              └────────────────────┘
```

## 2. Flujo Detallado de Scraping SNMP

```
PASO 1: Prometheus inicia scrape
─────────────────────────────────
┌────────────────┐
│  Prometheus    │
│  Scheduler     │
└────────┬───────┘
         │
         │ Timer tick (cada 30s)
         │ Target: snmp_exporter:9116/snmp
         │ Params: ?target=192.168.1.1&module=if_mib
         │
         ▼
┌────────────────────────────────────────────┐
│ HTTP GET Request                           │
│ GET http://snmp_exporter:9116/snmp?        │
│     target=192.168.1.1&module=if_mib       │
└────────────────────────────────────────────┘


PASO 2: SNMP Exporter procesa request
──────────────────────────────────────
┌────────────────────────────────────────────┐
│  SNMP Exporter                             │
├────────────────────────────────────────────┤
│  1. Parse URL parameters                   │
│     - target = 192.168.1.1                 │
│     - module = if_mib                      │
│                                            │
│  2. Carga configuración del módulo         │
│     - Lee snmp.yml                         │
│     - Obtiene lista de OIDs a consultar    │
│     - Obtiene auth (community/credentials) │
│                                            │
│  3. Construye SNMP queries                 │
│     OIDs a consultar:                      │
│     - 1.3.6.1.2.1.2.2.1.2  (ifDescr)       │
│     - 1.3.6.1.2.1.2.2.1.8  (ifOperStatus)  │
│     - 1.3.6.1.2.1.2.2.1.10 (ifInOctets)    │
│     - 1.3.6.1.2.1.2.2.1.16 (ifOutOctets)   │
│     - ... más OIDs según módulo            │
└────────────────────────────────────────────┘
         │
         │ SNMP GET Request
         │ UDP Packet to 192.168.1.1:161
         │ Community: "public" (v2c)
         │
         ▼


PASO 3: Dispositivo responde
─────────────────────────────
┌────────────────────────────────────────────┐
│  Dispositivo de Red (192.168.1.1)         │
├────────────────────────────────────────────┤
│  1. Recibe SNMP GET Request en puerto 161 │
│                                            │
│  2. Valida community string                │
│                                            │
│  3. Procesa cada OID solicitado            │
│     ifDescr.1 = "GigabitEthernet0/0"       │
│     ifOperStatus.1 = 1 (up)                │
│     ifInOctets.1 = 987654321               │
│     ifOutOctets.1 = 123456789              │
│     ... etc                                │
│                                            │
│  4. Empaqueta respuesta SNMP               │
└────────────────────────────────────────────┘
         │
         │ SNMP Response
         │ UDP Packet back to SNMP Exporter
         │
         ▼


PASO 4: SNMP Exporter convierte a Prometheus format
────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────┐
│  SNMP Exporter - Processing                           │
├────────────────────────────────────────────────────────┤
│  1. Recibe respuesta SNMP                             │
│                                                        │
│  2. Para cada OID en la respuesta:                    │
│     a) Mapea OID → Nombre de métrica                  │
│        1.3.6.1.2.1.2.2.1.8 → snmp_interface_status    │
│                                                        │
│     b) Extrae valor                                   │
│        ifOperStatus.1 = 1                             │
│                                                        │
│     c) Agrega labels                                  │
│        instance="192.168.1.1"                         │
│        ifIndex="1"                                    │
│        ifDescr="GigabitEthernet0/0"                   │
│                                                        │
│  3. Genera líneas de métrica Prometheus:              │
│                                                        │
│     # HELP snmp_interface_status Interface status     │
│     # TYPE snmp_interface_status gauge                │
│     snmp_interface_status{                            │
│       instance="192.168.1.1",                         │
│       ifIndex="1",                                    │
│       ifDescr="GigabitEthernet0/0"                    │
│     } 1                                               │
│                                                        │
│     snmp_interface_rx_bytes{                          │
│       instance="192.168.1.1",                         │
│       ifIndex="1",                                    │
│       ifDescr="GigabitEthernet0/0"                    │
│     } 987654321                                       │
│                                                        │
│     ... más métricas ...                              │
└────────────────────────────────────────────────────────┘
         │
         │ HTTP Response (text/plain)
         │ Content: Prometheus metrics format
         │
         ▼


PASO 5: Prometheus almacena métricas
─────────────────────────────────────
┌────────────────────────────────────────────┐
│  Prometheus Server                         │
├────────────────────────────────────────────┤
│  1. Recibe respuesta HTTP                  │
│                                            │
│  2. Parsea formato Prometheus              │
│                                            │
│  3. Agrega timestamp actual                │
│     timestamp = 1710684000 (epoch)         │
│                                            │
│  4. Almacena en TSDB:                      │
│     [metric_name, labels, timestamp, value]│
│                                            │
│  5. Mantiene en memoria para queries       │
│                                            │
│  6. Evalúa reglas de alertas sobre métricas│
│     IF snmp_interface_status == 2          │
│     THEN alert "Interface Down"            │
└────────────────────────────────────────────┘
```

## 3. Flujo de Alertas SNMP

```
MONITOREO CONTINUO
──────────────────

    ┌───────────────────────────────────────────┐
    │  Loop de evaluación cada 15s              │
    │  (Prometheus rule evaluation)             │
    └─────────────────┬─────────────────────────┘
                      │
                      ▼
    ┌───────────────────────────────────────────┐
    │  Prometheus evalúa reglas                 │
    │                                           │
    │  Rule: SNMPInterfaceDown                  │
    │  expr: snmp_interface_status == 2         │
    │  for: 5m                                  │
    └─────────────────┬─────────────────────────┘
                      │
                      │ Consulta TSDB
                      │ PromQL: snmp_interface_status == 2
                      ▼
    ┌───────────────────────────────────────────┐
    │  ¿Condición cumplida?                     │
    │                                           │
    │  snmp_interface_status{                   │
    │    instance="192.168.1.1",                │
    │    ifDescr="GigabitEthernet0/1"           │
    │  } = 2 (down)                             │
    └─────────────────┬─────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │ NO                      │ SI
         │ (status = 1 up)         │ (status = 2 down)
         ▼                         ▼
    ┌─────────┐         ┌───────────────────────┐
    │  OK     │         │ Inicia timer "for: 5m"│
    │ Continue│         │ Espera 5 minutos      │
    └─────────┘         └───────────┬───────────┘
         △                          │
         │                          │
         │              ┌───────────┴────────────┐
         │              │ ¿Sigue down después    │
         │              │  de 5 minutos?         │
         │              └───────────┬────────────┘
         │                          │
         │ NO                       │ SI
         │ (volvió a up)            │
         └──────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────┐
    │  ALERTA DISPARA (FIRING)                  │
    │                                           │
    │  Alert: SNMPInterfaceDown                 │
    │  Status: firing                           │
    │  StartsAt: 2024-01-15T10:35:00Z           │
    │  Labels:                                  │
    │    alertname: SNMPInterfaceDown           │
    │    severity: critical                     │
    │    instance: 192.168.1.1                  │
    │    ifDescr: GigabitEthernet0/1            │
    │  Annotations:                             │
    │    summary: Interface is DOWN             │
    └─────────────────┬─────────────────────────┘
                      │
                      │ HTTP POST (JSON)
                      ▼
    ┌───────────────────────────────────────────┐
    │  Alertmanager                             │
    │                                           │
    │  1. Recibe alerta de Prometheus           │
    │  2. Agrupa alertas similares              │
    │  3. Aplica routing rules                  │
    │  4. Suprime duplicados                    │
    │  5. Aplica silences (si existen)          │
    └─────────────────┬─────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Email     │ │   Slack     │ │  Webhook    │
│ Notification│ │ Notification│ │  to Django  │
│             │ │             │ │             │
│ To: ops@... │ │ Channel:    │ │ POST /api/  │
│ Subject:    │ │ #alerts     │ │ webhook/    │
│ Interface   │ │             │ │ alerts      │
│ Down        │ │ Message:    │ │             │
└─────────────┘ │ :warning:   │ └──────┬──────┘
                │ Interface   │        │
                │ Down on     │        │
                │ 192.168.1.1 │        │
                └─────────────┘        │
                                       ▼
                           ┌─────────────────────┐
                           │  Django API         │
                           │                     │
                           │  1. Recibe webhook  │
                           │  2. Valida payload  │
                           │  3. Crea registro:  │
                           │     SNMPAlert(      │
                           │       device=...,   │
                           │       type="down",  │
                           │       severity=...  │
                           │     )               │
                           │  4. Guarda en DB    │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │  PostgreSQL         │
                           │                     │
                           │  INSERT INTO        │
                           │  metrics_snmpalert  │
                           │  ...                │
                           └─────────────────────┘
```

## 4. Flujo de Sincronización de Dispositivos (Django → SNMP Exporter)

```
GESTIÓN DINÁMICA DE TARGETS
────────────────────────────

    ┌─────────────────────────────────────┐
    │  Usuario / Administrador            │
    └──────────────┬──────────────────────┘
                   │
                   │ HTTP POST
                   │ /api/snmp/devices/
                   │ {
                   │   "name": "new-switch",
                   │   "address": "192.168.1.25",
                   │   ...
                   │ }
                   ▼
    ┌─────────────────────────────────────┐
    │  Django REST API                    │
    │  (api/views.py)                     │
    │                                     │
    │  1. Valida datos                    │
    │  2. Crea SNMPDevice en DB           │
    │  3. Dispara task Celery             │
    └──────────────┬──────────────────────┘
                   │
                   │ Task: generate_snmp_targets_config.delay()
                   ▼
    ┌─────────────────────────────────────┐
    │  Celery Worker                      │
    │  (metrics/tasks.py)                 │
    │                                     │
    │  Task: generate_snmp_targets_config │
    │                                     │
    │  1. Query DB:                       │
    │     SNMPDevice.objects.filter(      │
    │       enabled=True                  │
    │     )                               │
    │                                     │
    │  2. Construye estructura JSON:      │
    │     {                               │
    │       "devices": [                  │
    │         {                           │
    │           "name": "new-switch",     │
    │           "address": "192.168.1.25",│
    │           "port": 161,              │
    │           ...                       │
    │         },                          │
    │         ...                         │
    │       ]                             │
    │     }                               │
    │                                     │
    │  3. Escribe archivo:                │
    │     /etc/snmp_exporter/targets.json │
    └──────────────┬──────────────────────┘
                   │
                   │ File updated
                   ▼
    ┌─────────────────────────────────────┐
    │  Actualizar Prometheus Config       │
    │                                     │
    │  Opción A: Dynamic file_sd_configs  │
    │  - Prometheus detecta cambio auto   │
    │  - Relee targets cada 5m            │
    │                                     │
    │  Opción B: Reload manual            │
    │  - HTTP POST /-/reload              │
    │  - Requiere --web.enable-lifecycle  │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  Prometheus                         │
    │                                     │
    │  • Detecta nuevo target             │
    │  • Inicia scraping                  │
    │    192.168.1.25 (new-switch)        │
    │  • Métricas disponibles en ~30s     │
    └─────────────────────────────────────┘
```

## 5. Flujo de Consulta en Dashboard Grafana

```
VISUALIZACIÓN DE MÉTRICAS
─────────────────────────

    ┌─────────────────────────────────────┐
    │  Usuario abre Dashboard Grafana     │
    │  "SNMP Network Monitoring"          │
    └──────────────┬──────────────────────┘
                   │
                   │ HTTP GET
                   ▼
    ┌─────────────────────────────────────┐
    │  Grafana Server                     │
    │                                     │
    │  Panel: "Interface Traffic"         │
    │  Query configurado:                 │
    │                                     │
    │  rate(snmp_interface_rx_bytes[5m])  │
    └──────────────┬──────────────────────┘
                   │
                   │ PromQL Query
                   │ HTTP POST /api/v1/query_range
                   │ {
                   │   query: "rate(...)",
                   │   start: "2024-01-15T10:00:00Z",
                   │   end: "2024-01-15T12:00:00Z",
                   │   step: "15s"
                   │ }
                   ▼
    ┌─────────────────────────────────────┐
    │  Prometheus Server                  │
    │                                     │
    │  1. Parsea PromQL                   │
    │  2. Consulta TSDB                   │
    │  3. Calcula rate() para cada serie  │
    │  4. Retorna time series             │
    └──────────────┬──────────────────────┘
                   │
                   │ JSON Response
                   │ {
                   │   "data": {
                   │     "resultType": "matrix",
                   │     "result": [
                   │       {
                   │         "metric": {
                   │           "instance": "192.168.1.1",
                   │           "ifDescr": "GigE0/0"
                   │         },
                   │         "values": [
                   │           [1705318800, "12500000"],
                   │           [1705318815, "13200000"],
                   │           ...
                   │         ]
                   │       }
                   │     ]
                   │   }
                   │ }
                   ▼
    ┌─────────────────────────────────────┐
    │  Grafana Rendering                  │
    │                                     │
    │  1. Procesa series                  │
    │  2. Aplica transformaciones         │
    │     (ej: bytes → MB/s)              │
    │  3. Renderiza gráfico               │
    │  4. Envía HTML/JS al browser        │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  Browser muestra gráfico            │
    │                                     │
    │  [Gráfico de líneas]                │
    │   GigE0/0: 125 MB/s ────────        │
    │   GigE0/1: 85 MB/s  ──────          │
    │   GigE0/2: 42 MB/s  ────            │
    │                                     │
    │  Período: 10:00 - 12:00             │
    └─────────────────────────────────────┘
```

## Notas

- Todos los flujos son continuos y se repiten periódicamente
- Los tiempos de scrape son configurables (default: 30s para SNMP)
- Las alertas tienen delays configurables (for: 5m, etc.)
- La sincronización de dispositivos puede ser manual o automática
- Los dashboards se actualizan en tiempo real (auto-refresh)
