# Software Runbook

This is the end-to-end software setup guide.

## 1. Local Development

```bash
git clone https://github.com/darrylsj/x402-temperature-server.git
cd x402-temperature-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[dev]'
python -m pytest
cd proxy && npm install && npm test && cd ..
./scripts/test-both-architectures.sh
python -m x402_temperature_server
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8080
```

Test:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/temperature
curl http://127.0.0.1:8080/.well-known/x402-temperature.json
```

## 2. Raspberry Pi OS Prep

Install Raspberry Pi OS Lite, connect Wi-Fi, and SSH into the Pi.

Update the system:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Install required packages:

```bash
sudo apt install -y git python3-venv python3-pip i2c-tools
```

## 3. Enable I2C For BME280

```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

Check the sensor:

```bash
i2cdetect -y 1
```

Look for `76` or `77`.

## 4. Install The App On The Pi

```bash
git clone https://github.com/darrylsj/x402-temperature-server.git
cd x402-temperature-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[sensor]'
cp .env.example .env
```

Edit `.env`:

```bash
SENSOR_BACKEND=bme280
STATION_ID=roof-demo-01
LOCATION_LABEL=Neighborhood station
LATITUDE=37.33
LONGITUDE=-121.89
READING_TTL_SECONDS=60
I2C_ADDRESS=0x76
ENABLE_X402=false
```

Run:

```bash
python -m x402_temperature_server
```

From another machine on the same network:

```bash
curl http://PI_ADDRESS:8080/temperature
```

## 5. Install As A systemd Service

From the repo directory on the Pi:

```bash
sudo mkdir -p /opt
sudo cp -R "$PWD" /opt/x402-temperature-server
sudo cp systemd/x402-temperature-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x402-temperature-server
sudo systemctl status x402-temperature-server
```

Read logs:

```bash
journalctl -u x402-temperature-server -f
```

## 6. Cloud Collector Design

In this design the Pi posts readings to a cloud server and the cloud server handles x402.

Pi responsibilities:

- read sensor
- sign or authenticate each reading with a station token
- post every 60 seconds
- retry on network failure

Cloud responsibilities:

- validate station token
- reject impossible or stale readings
- store latest reading per station
- expose free health and manifest endpoints
- expose paid x402 endpoint for latest reading

Suggested endpoints:

```text
POST /sensor-readings
GET /health
GET /.well-known/x402-temperature.json
GET /temperature/latest
```

Enable the runnable in-memory collector:

```bash
ENABLE_CLOUD_COLLECTOR=true
STATION_ID=roof-demo-01
STATION_INGEST_TOKEN=replace-with-random-token
READING_TTL_SECONDS=180
INGEST_MAX_AGE_SECONDS=900
```

For a no-hardware demo, keep `SENSOR_BACKEND=simulated` and post a simulated reading with the same schema.

Example Pi-to-cloud post:

```bash
curl -X POST https://YOUR-CLOUD-HOST/sensor-readings \
  -H 'Content-Type: application/json' \
  -H 'X-Station-Token: replace-with-random-token' \
  -d '{
    "station": "roof-demo-01",
    "celsius": 21.42,
    "humidity": 48.3,
    "pressure_hpa": 1013.2,
    "read_at": "2026-08-12T08:00:00Z",
    "battery_percent": 84,
    "battery_voltage": 5.08
  }'
```

Example buyer-facing latest-reading request:

```bash
curl https://YOUR-CLOUD-HOST/temperature/latest
```

Freshness policy:

```text
fresh: <= 180 seconds
stale but returnable: <= 900 seconds
expired: > 900 seconds
```

## 7. Self-Contained Pi x402 Design

In this design the Pi handles both sensor reading and paid serving.

Recommended shape:

```text
public HTTPS
  -> Node/Express x402 Gateway proxy
  -> localhost:8080 FastAPI sensor service
```

This keeps the Python app simple and lets Circle's current Gateway Nanopayments seller middleware handle the payment layer.

Run the local mock-payment proxy:

```bash
cd proxy
ARCHITECTURE=edge \
X402_GATEWAY_MODE=mock \
SENSOR_ORIGIN=http://127.0.0.1:8080 \
npm start
```

An unpaid call to `GET /temperature` returns `402`; a local test call with `x-payment: test-paid` returns the forwarded JSON. Use `X402_GATEWAY_MODE=circle` only for a real Circle Gateway test after confirming the seller address, chain/network, URL, and amount.

If the sample host does not have Node, use the Python mock gate:

```bash
ENABLE_MOCK_X402=true python -m x402_temperature_server
curl -i http://127.0.0.1:8080/temperature
curl -H 'x-payment: test-paid' http://127.0.0.1:8080/temperature
```

This proves the same unpaid-402 and paid-200 endpoint contract without installing Node or moving USDC.

Ingress options:

- Cloudflare Tunnel
- Tailscale Funnel
- Caddy with port forwarding
- Nginx with TLS and port forwarding

## 8. Direct FastAPI x402 Educational Mode

The repo includes an optional direct FastAPI x402 switch:

```bash
python -m pip install '.[sensor,x402]'
```

Then set:

```bash
ENABLE_X402=true
X402_PRICE_USD=0.001
X402_NETWORK=base
PAY_TO_EVM_ADDRESS=0xYourReceivingWallet
```

This path is useful for learning, but the recommended production path is the Gateway payment proxy described above.

## 9. Verification Checklist

Before calling the station production-ready:

- `python -m pytest` passes.
- `/health` returns `ok: true`.
- `/temperature` returns real sensor values.
- Coordinates are rounded.
- Sensor timestamp is current.
- Response includes `age_seconds` and `stale`.
- Service restarts after reboot.
- Logs show no sensor read errors.
- Free manifest is reachable.
- Unpaid paid-resource request returns `402`.
- Paid request returns `200` and the JSON payload.
- Public docs do not expose private keys, wallet secrets, exact home coordinates, or internal tokens.
