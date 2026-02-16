# Guía Rápida de Referencia SNMP

## Comandos Útiles SNMP

### 1. Testing SNMP desde línea de comandos

```bash
# Instalar herramientas SNMP
apt-get install snmp snmp-mibs-downloader

# Test SNMP v2c
snmpwalk -v2c -c public 192.168.1.1

# Test interface específica
snmpget -v2c -c public 192.168.1.1 1.3.6.1.2.1.2.2.1.8.1

# Test SNMPv3
snmpwalk -v3 -l authPriv -u admin -a SHA -A authpass -x AES -X privpass 192.168.1.1

# Listar interfaces
snmpwalk -v2c -c public 192.168.1.1 IF-MIB::ifDescr
```

### 2. OIDs Comunes

```
# System Information
1.3.6.1.2.1.1.1.0       - sysDescr (Descripción del sistema)
1.3.6.1.2.1.1.3.0       - sysUpTime (Tiempo de actividad)
1.3.6.1.2.1.1.5.0       - sysName (Nombre del sistema)
1.3.6.1.2.1.1.6.0       - sysLocation (Ubicación)
1.3.6.1.2.1.1.4.0       - sysContact (Contacto)

# Network Interfaces
1.3.6.1.2.1.2.2.1.2     - ifDescr (Nombres)
1.3.6.1.2.1.2.2.1.8     - ifOperStatus (Estado: 1=up, 2=down)
1.3.6.1.2.1.2.2.1.10    - ifInOctets (Bytes recibidos)
1.3.6.1.2.1.2.2.1.16    - ifOutOctets (Bytes enviados)
1.3.6.1.2.1.2.2.1.14    - ifInErrors (Errores entrada)
1.3.6.1.2.1.2.2.1.20    - ifOutErrors (Errores salida)

# Cisco Specific
1.3.6.1.4.1.9.9.109.1.1.1.1.7   - cpmCPUTotal5minRev (CPU %)
1.3.6.1.4.1.9.9.48.1.1.1.5      - ciscoMemoryPoolUsed
1.3.6.1.4.1.9.9.48.1.1.1.6      - ciscoMemoryPoolFree
```

### 3. Configuración Rápida Docker

```yaml
# Agregar al docker-compose.yml
services:
  snmp_exporter:
    image: prom/snmp-exporter:latest
    ports:
      - "9116:9116"
    volumes:
      - ./snmp-exporter:/etc/snmp_exporter
    networks:
      - prueba
```

```bash
# Crear directorio
mkdir -p snmp-exporter

# Iniciar servicio
docker-compose up -d snmp_exporter

# Ver logs
docker-compose logs -f snmp_exporter

# Test endpoint
curl http://localhost:9116/metrics
curl http://localhost:9116/snmp?target=192.168.1.1&module=if_mib
```

### 4. Prometheus Queries Útiles

```promql
# Ver estado de todos los dispositivos
up{job="snmp_devices"}

# Interfaces caídas
snmp_interface_status{ifOperStatus="2"}

# Tráfico total en MB/s
sum(rate(snmp_interface_rx_bytes[5m])) / 1024 / 1024

# Dispositivos con errores
count by (instance) (rate(snmp_interface_rx_errors[5m]) > 10)

# Uptime de dispositivos
snmp_sysUpTime / 100 / 86400  # en días
```

### 5. Troubleshooting

```bash
# Verificar conectividad SNMP
docker exec snmp_exporter snmpwalk -v2c -c public <device-ip>

# Ver configuración cargada
docker exec snmp_exporter cat /etc/snmp_exporter/snmp.yml

# Verificar logs de Prometheus
docker-compose logs prometheus | grep snmp

# Test manual de scrape
curl -s 'http://localhost:9116/snmp?target=192.168.1.1&module=if_mib' | grep interface

# Verificar tiempo de respuesta
time curl -s 'http://localhost:9116/snmp?target=192.168.1.1&module=if_mib' > /dev/null
```

### 6. Configuración de Dispositivos

#### Cisco IOS
```
! Configurar SNMP v2c
snmp-server community public RO
snmp-server location "Datacenter 1"
snmp-server contact "admin@example.com"

! Configurar SNMP v3
snmp-server group snmpv3group v3 priv
snmp-server user snmpv3user snmpv3group v3 auth sha authpass priv aes 128 privpass
snmp-server view all iso included

! Configurar ACL
access-list 99 permit 192.168.100.10
snmp-server community public RO 99
```

#### Linux (Net-SNMP)
```bash
# Instalar
apt-get install snmpd

# Editar /etc/snmp/snmpd.conf
rocommunity public 192.168.100.10
syslocation "Datacenter 1, Rack 5"
syscontact admin@example.com

# Reiniciar
systemctl restart snmpd
systemctl enable snmpd

# Verificar
systemctl status snmpd
netstat -tulpn | grep 161
```

### 7. API Django - Ejemplos cURL

```bash
# Listar dispositivos SNMP
curl http://localhost/api/snmp/devices/

# Agregar dispositivo
curl -X POST http://localhost/api/snmp/devices/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "router-01",
    "address": "192.168.1.1",
    "port": 161,
    "community": "public",
    "version": "2c",
    "snmp_module": "if_mib",
    "vendor": "cisco",
    "device_type": "router",
    "site": "datacenter-1"
  }'

# Ver interfaces de un dispositivo
curl http://localhost/api/snmp/devices/1/interfaces/

# Sincronizar configuración
curl -X POST http://localhost/api/snmp/devices/sync-config/

# Ver alertas SNMP
curl http://localhost/api/snmp/alerts/
```

### 8. Alertas - Template Ejemplo

```yaml
# prometheus/snmp_alerts.yml
groups:
  - name: snmp_basic
    rules:
      - alert: InterfaceDown
        expr: snmp_interface_status == 2
        for: 5m
        annotations:
          summary: "Interface {{ $labels.ifDescr }} is DOWN"
          
      - alert: HighTraffic
        expr: rate(snmp_interface_rx_bytes[5m]) > 1e9
        for: 10m
        annotations:
          summary: "High traffic on {{ $labels.ifDescr }}"
```

### 9. Grafana - Ejemplo de Panel

```json
{
  "title": "Interface Status",
  "targets": [
    {
      "expr": "snmp_interface_status",
      "legendFormat": "{{instance}}-{{ifDescr}}"
    }
  ],
  "valueMaps": [
    { "value": "1", "text": "UP" },
    { "value": "2", "text": "DOWN" }
  ]
}
```

### 10. Mantenimiento Común

```bash
# Recargar configuración Prometheus (sin reiniciar)
curl -X POST http://localhost:9090/prometheus/-/reload

# Ver targets activos
curl http://localhost:9090/prometheus/api/v1/targets | jq .

# Verificar reglas de alertas
curl http://localhost:9090/prometheus/api/v1/rules | jq .

# Backup de métricas
docker exec prometheus promtool tsdb dump /prometheus > backup.txt

# Ver estadísticas de SNMP exporter
curl http://localhost:9116/metrics | grep snmp_scrape
```

## Checklist de Implementación

- [ ] SNMP exporter instalado y funcionando
- [ ] Al menos 1 dispositivo de prueba configurado
- [ ] Prometheus scrapeando métricas SNMP
- [ ] Alertas básicas configuradas
- [ ] Dashboard Grafana creado
- [ ] Modelos Django migrados
- [ ] API REST funcionando
- [ ] Documentación actualizada
- [ ] Equipo capacitado

## Recursos Adicionales

- **SNMP Exporter**: https://github.com/prometheus/snmp_exporter
- **Generator Tool**: https://github.com/prometheus/snmp_exporter/tree/main/generator
- **MIBs Database**: https://oidref.com/
- **Net-SNMP**: http://www.net-snmp.org/
- **Cisco SNMP**: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/snmp/configuration/15-mt/snmp-15-mt-book.html

## Notas de Seguridad

⚠️ **IMPORTANTE:**
- Nunca usar community string "public" en producción
- Preferir SNMPv3 sobre v1/v2c
- Implementar ACLs en dispositivos
- Rotar credenciales periódicamente
- Limitar acceso por IP/firewall
- Monitorear intentos de acceso fallidos
- Cifrar credenciales en variables de entorno
- No exponer puerto 161 a Internet

## Contacto y Soporte

Para preguntas sobre la implementación SNMP:
- Email: admin@example.com
- Slack: #monitoring-snmp
- Documentación completa: `SNMP_IMPLEMENTATION_SCHEMA.md`
