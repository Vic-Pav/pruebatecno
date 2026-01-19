import time
from django.utils.deprecation import MiddlewareMixin
from influxdb_client import InfluxDBClient, Point
import os


class InfluxMetricsMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        super().__init__(get_response)

        self.client = InfluxDBClient(
            url=os.getenv("INFLUX_URL"),
            token=os.getenv("INFLUX_TOKEN"),
            org=os.getenv("INFLUX_ORG"),
        )
        self.write_api = self.client.write_api()

        self.bucket = os.getenv("INFLUX_BUCKET")

    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        duration = time.time() - getattr(request, "_start_time", time.time())

        point = (
            Point("django_http_requests")
            .tag("method", request.method)
            .tag("path", request.path)
            .field("status_code", response.status_code)
            .field("duration", duration)
        )

        try:
            self.write_api.write(bucket=self.bucket, record=point)
        except Exception as e:
            print(f"[Influx middleware error] {e}")

        return response