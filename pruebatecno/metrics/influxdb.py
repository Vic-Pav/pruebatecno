from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os

INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "mytoken")
INFLUX_ORG = os.getenv("INFLUX_ORG", "prueba")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "metrics")

client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
)

write_api = client.write_api(write_options=SYNCHRONOUS)


def write_request_metric(path, method, status_code, duration_ms):
    point = (
        Point("django_requests")
        .tag("path", path)
        .tag("method", method)
        .field("status_code", status_code)
        .field("duration_ms", duration_ms)
    )

    write_api.write(bucket=INFLUX_BUCKET, record=point)

