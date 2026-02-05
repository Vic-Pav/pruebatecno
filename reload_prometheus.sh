#!/bin/bash
while inotifywait -e close_write ./prometheus/alerts.yml; do
  curl -X POST http://localhost/prometheus/-/reload
  echo "Prometheus recargado 🔄"
done

