import os
import logging
from xmlrpc import client

from django.http import HttpRequest
from django_prometheus import exports
from django.core.cache import cache
from prometheus_client import Gauge, CollectorRegistry, generate_latest
from django.core.cache import cache
from influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)

url = os.getenv('INFLUX_URL', 'http://influxdb:8086')
token = os.getenv('INFLUX_TOKEN', 'mytoken')
org = os.getenv('INFLUX_ORG', 'prueba')
flux = 'from(bucket:"metrics") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "metricas_pc") |> last()'

def fetch_influx_metrics():
    cache_key = "influx_latest_metrics"
    data = cache.get(cache_key)

    if data is not None:
        return data  # ✅ salir rápido

    results = {}

    try:
        with InfluxDBClient(url=url, token=token, org=org) as client:
            query_api = client.query_api()
            tables = query_api.query(flux)

            for table in tables:
                for record in table.records:
                    field = record.get_field()
                    value = record.get_value()
                    try:
                        results[field] = float(value)
                    except Exception:
                        logger.exception("Parsing error for %s", field)

        # ✅ SOLO cachea si fue exitoso
        cache.set(cache_key, results, timeout=10)

    except Exception:
        logger.exception("Influx query failed")
        return {}  # no cachear errores

    return results




def metrics_with_influx(request: HttpRequest):
	"""Wrapper view: fetch Influx values, render them in a temp registry and
	append them to the standard django_prometheus output.
	"""
	influx_vals = fetch_influx_metrics()
	logger.info('metrics_with_influx fetched Influx values: %s', influx_vals)
	base_response = exports.ExportToDjangoView(request)
	# Ensure we correctly read response bytes (handle streaming responses)
	if getattr(base_response, 'streaming', False):
		base_content = b"".join(base_response.streaming_content)
	else:
		base_content = base_response.content
	# Create a temporary registry with the Influx-derived gauges
	temp_reg = CollectorRegistry()
	if 'Uso_CPU' in influx_vals:
		g = Gauge('Uso_CPU', 'Uso de CPU', registry=temp_reg)
		g.set(influx_vals['Uso_CPU'])
	if 'Uso_RAM' in influx_vals:
		g = Gauge('Uso_RAM', 'Uso de RAM', registry=temp_reg)
		g.set(influx_vals['Uso_RAM'])
	influx_metrics = generate_latest(temp_reg)
	logger.info('metrics_with_influx: base_content=%d bytes, influx_metrics=%d bytes, keys=%s',
		len(base_content), len(influx_metrics), list(influx_vals.keys()))
	# Concatenate bytes
	combined = base_content + b"\n" + influx_metrics
	from django.http import HttpResponse
	return HttpResponse(combined, content_type=base_response['Content-Type'])


def metrics_influx_only(request: HttpRequest):
	"""Return only the Influx-derived gauges as Prometheus exposition format."""
	influx_vals = fetch_influx_metrics()
	temp_reg = CollectorRegistry()
	if 'Uso_CPU' in influx_vals:
		g = Gauge('Uso_CPU', 'Uso de CPU', registry=temp_reg)
		g.set(influx_vals['Uso_CPU'])
	if 'Uso_RAM' in influx_vals:
		g = Gauge('Uso_RAM', 'Uso de RAM', registry=temp_reg)
		g.set(influx_vals['Uso_RAM'])
	data = generate_latest(temp_reg)
	from django.http import HttpResponse
	return HttpResponse(data, content_type='text/plain; version=0.0.4; charset=utf-8')
