import os
import logging

from django.shortcuts import render
from django.http import HttpRequest
from django_prometheus import exports

from prometheus_client import Gauge, REGISTRY, CollectorRegistry, generate_latest

from influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


def fetch_influx_metrics():
	"""Return latest Influx values as a dict: {'Uso_CPU': val, 'Uso_RAM': val}.

	Avoids relying on shared Gauge objects across processes; callers can
	render these into a temporary registry per-request.
	"""
	url = os.getenv('INFLUX_URL', 'http://influxdb:8086')
	token = os.getenv('INFLUX_TOKEN', 'mytoken')
	org = os.getenv('INFLUX_ORG', 'prueba')
	results = {}
	try:
		client = InfluxDBClient(url=url, token=token, org=org)
		query_api = client.query_api()
		flux = 'from(bucket:"metrics") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "metricas_pc") |> last()'
		tables = query_api.query(flux)
		for table in tables:
			for record in table.records:
				field = record.get_field()
				value = record.get_value()
				try:
					results[field] = float(value)
				except Exception:
					logger.exception('Failed parsing Influx value for %s', field)
	except Exception:
		logger.exception('Failed to query InfluxDB at %s', url)
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
