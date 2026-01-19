from influxdb_client import InfluxDBClient
import os

client = InfluxDBClient(
    url=os.getenv("INFLUX_URL"),
    token=os.getenv("INFLUX_TOKEN"),
    org=os.getenv("INFLUX_ORG"),
)

def get_latest_metrics():
    query = """
    from(bucket: "metricas_pc")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "metricas_pc")
      |> last()
    """

    tables = client.query_api().query(query)
    results = []

    for table in tables:
        for record in table.records:
            results.append({
                "campo": record.get_field(),
                "valor": record.get_value(),
                "tiempo": record.get_time(),
            })

    return results