import psutil
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

client = InfluxDBClient(
    url="http://localhost:8086",
    token="mytoken",
    org="prueba"
)

write_api = client.write_api(write_options=SYNCHRONOUS)

while True:
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent

    point = (
        Point("metricas_pc")
        .field("Uso_CPU", cpu)
        .field("Uso_RAM", mem)
    )

    write_api.write(
        bucket="metrics",
        record=point
    )

    print(f"CPU={cpu}% MEM={mem}%")
    time.sleep(5)