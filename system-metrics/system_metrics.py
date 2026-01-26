import os
import time
import logging
import psutil
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from urllib.error import URLError

# Config desde entorno con defaults adecuados para ejecución en host
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "mytoken")
INFLUX_ORG = os.getenv("INFLUX_ORG", "prueba")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "metrics")
INTERVAL_SECS = float(os.getenv("INTERVAL_SECS", "5"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def wait_for_influx(url: str, timeout: float = 30.0, step: float = 2.0) -> None:
    import urllib.request, json, time
    deadline = time.time() + timeout
    health_url = url.rstrip("/") + "/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "pass":
                        logging.info("Influx health OK at %s", health_url)
                        return
        except Exception as e:
            logging.warning("Influx not ready at %s: %s", health_url, e)
        time.sleep(step)
    raise RuntimeError(f"Influx not ready after {timeout}s at {health_url}")

def main():
    logging.info(
        "Starting system-metrics writer to %s (org=%s, bucket=%s, interval=%ss)",
        INFLUX_URL, INFLUX_ORG, INFLUX_BUCKET, INTERVAL_SECS,
    )

    # Espera a que Influx responda en el puerto publicado
    wait_for_influx(INFLUX_URL, timeout=60, step=3)

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    while True:
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent

            point = Point("metricas_pc").field("Uso_CPU", cpu).field("Uso_RAM", mem)

            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logging.info("Wrote metricas_pc: CPU=%.1f%% MEM=%.1f%%", cpu, mem)
        except Exception as e:
            logging.exception("Failed to write to Influx at %s", INFLUX_URL)
        finally:
            time.sleep(INTERVAL_SECS)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Fatal error in system-metrics")
        raise