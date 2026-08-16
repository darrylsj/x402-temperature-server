#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
EDGE_SENSOR_PORT="${EDGE_SENSOR_PORT:-18080}"
CLOUD_SENSOR_PORT="${CLOUD_SENSOR_PORT:-18081}"
EDGE_PROXY_PORT="${EDGE_PROXY_PORT:-18082}"
CLOUD_PROXY_PORT="${CLOUD_PROXY_PORT:-18083}"
TOKEN="${STATION_INGEST_TOKEN:-local-test-token}"

pids=()

cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

wait_for() {
  local url="$1"
  for _ in $(seq 1 80); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

assert_status() {
  local expected="$1"
  local url="$2"
  local status
  shift 2
  status="$(curl -s -o /tmp/x402-temp-response.json -w '%{http_code}' "$@" "$url")"
  if [[ "$status" != "$expected" ]]; then
    echo "Expected $expected from $url, got $status" >&2
    cat /tmp/x402-temp-response.json >&2 || true
    return 1
  fi
}

cd "$ROOT_DIR"

SENSOR_BACKEND=simulated HOST=127.0.0.1 PORT="$EDGE_SENSOR_PORT" "$PYTHON_BIN" -m x402_temperature_server >/tmp/x402-temp-edge.log 2>&1 &
pids+=("$!")

SENSOR_BACKEND=simulated ENABLE_CLOUD_COLLECTOR=true STATION_INGEST_TOKEN="$TOKEN" HOST=127.0.0.1 PORT="$CLOUD_SENSOR_PORT" "$PYTHON_BIN" -m x402_temperature_server >/tmp/x402-temp-cloud.log 2>&1 &
pids+=("$!")

wait_for "http://127.0.0.1:${EDGE_SENSOR_PORT}/health"
wait_for "http://127.0.0.1:${CLOUD_SENSOR_PORT}/health"

READ_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
curl -fsS -X POST "http://127.0.0.1:${CLOUD_SENSOR_PORT}/sensor-readings" \
  -H 'Content-Type: application/json' \
  -H "X-Station-Token: ${TOKEN}" \
  -d "{\"station\":\"danville-demo-01\",\"celsius\":22.22,\"humidity\":54.0,\"pressure_hpa\":1017.0,\"read_at\":\"${READ_AT}\",\"battery_percent\":84,\"battery_voltage\":5.08}" >/dev/null

cd "$ROOT_DIR/proxy"

ARCHITECTURE=edge X402_GATEWAY_MODE=mock SENSOR_ORIGIN="http://127.0.0.1:${EDGE_SENSOR_PORT}" PORT="$EDGE_PROXY_PORT" npm start >/tmp/x402-temp-edge-proxy.log 2>&1 &
pids+=("$!")

ARCHITECTURE=cloud X402_GATEWAY_MODE=mock SENSOR_ORIGIN="http://127.0.0.1:${CLOUD_SENSOR_PORT}" PORT="$CLOUD_PROXY_PORT" npm start >/tmp/x402-temp-cloud-proxy.log 2>&1 &
pids+=("$!")

wait_for "http://127.0.0.1:${EDGE_PROXY_PORT}/health"
wait_for "http://127.0.0.1:${CLOUD_PROXY_PORT}/health"

assert_status 402 "http://127.0.0.1:${EDGE_PROXY_PORT}/temperature"
assert_status 200 "http://127.0.0.1:${EDGE_PROXY_PORT}/temperature" -H 'x-payment: test-paid'

assert_status 402 "http://127.0.0.1:${CLOUD_PROXY_PORT}/temperature/latest"
assert_status 200 "http://127.0.0.1:${CLOUD_PROXY_PORT}/temperature/latest" -H 'x-payment: test-paid'

echo "Both local x402 architecture tests passed."
