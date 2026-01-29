import os
import time
import logging
import psutil
from prometheus_client import Gauge, start_http_server

# Influx opcional
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9153"))
INTERVAL_SECS = float(os.getenv("INTERVAL_SECS", "5"))

# Toggle de escritura a Influx (por defecto activada)
ENABLE_INFLUX_WRITE = os.getenv("ENABLE_INFLUX_WRITE", "1") == "1"
INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")  # dentro de Docker
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "mytoken")
INFLUX_ORG = os.getenv("INFLUX_ORG", "prueba")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "metrics")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Gauges expuestos al scrape de Prometheus
cpu_g = Gauge("Uso_CPU", "Uso de CPU (%)")
ram_g = Gauge("Uso_RAM", "Uso de RAM (%)")
influx_up = Gauge("influx_up", "Salud de la consulta/escritura a Influx (1=OK, 0=fallo)")

client = None
write_api = None

def init_influx():
    global client, write_api
    if not ENABLE_INFLUX_WRITE:
        logging.info("Influx write disabled by ENABLE_INFLUX_WRITE=0")
        return
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    logging.info("Influx client initialized for %s (org=%s, bucket=%s)", INFLUX_URL, INFLUX_ORG, INFLUX_BUCKET)

def write_influx(cpu: float, ram: float):
    if not ENABLE_INFLUX_WRITE or write_api is None:
        return
    try:
        point = Point("metricas_pc").field("Uso_CPU", cpu).field("Uso_RAM", ram)
        write_api.write(bucket=INFLUX_BUCKET, record=point)
        influx_up.set(1)
    except Exception as e:
        influx_up.set(0)
        logging.warning("Failed to write to Influx: %s", e)

def collect_once():
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    cpu_g.set(cpu)
    ram_g.set(mem)
    write_influx(cpu, mem)

if __name__ == "__main__":
    # Arranca servidor HTTP /metrics
    start_http_server(EXPORTER_PORT)
    logging.info("System metrics exporter listening on :%d", EXPORTER_PORT)
    init_influx()
    while True:
        try:
            collect_once()
        except Exception as e:
            logging.exception("Exporter collection error: %s", e)
        time.sleep(INTERVAL_SECS)