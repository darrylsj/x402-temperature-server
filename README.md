# x402 Temperature Server

This is the companion implementation for the weather-bot chapter of *The x402 Handbook*: a Raspberry Pi endpoint that sells a live hyperlocal temperature reading for a tiny USDC payment.

The book keeps the idea short. This repo carries the operational detail: sensor backends, tests, Raspberry Pi setup notes, sample output, systemd service, and the production x402 switch.

## What It Sells

`GET /temperature` returns a fresh reading from the station:

```json
{
  "station": "roof-demo-01",
  "location": "Neighborhood station",
  "celsius": 21.42,
  "fahrenheit": 70.56,
  "humidity": 48.3,
  "pressure_hpa": 1013.2,
  "read_at": "2026-08-12T08:00:00Z",
  "ttl_seconds": 60,
  "lat": 37.33,
  "lon": -121.89
}
```

The latitude and longitude are rounded on purpose. Sell the weather near you, not your doorstep.

## Hardware

Minimum build:

- Raspberry Pi Zero 2 W or Zero WH
- 32GB microSD card
- Micro USB power supply
- BME280 sensor for temperature, humidity, and pressure
- Female-to-female jumper wires, or a STEMMA/Qwiic adapter path
- Small case or enclosure

Optional outdoor build:

- DS18B20 waterproof temperature probe
- 4.7k resistor for the DS18B20 data pull-up
- Weatherproof enclosure and radiation shield
- Solar panel, charge controller, and battery after the first wired version is stable

## Local Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[dev]'
python -m pytest
python -m x402_temperature_server
```

Local development uses `SENSOR_BACKEND=mock` and `ENABLE_X402=false`, so tests run without hardware, secrets, or blockchain access.

Try it:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/temperature
curl http://127.0.0.1:8080/.well-known/x402-temperature.json
```

## Raspberry Pi Setup

The detailed Pi wiring and service setup is in [docs/raspberry-pi-build.md](docs/raspberry-pi-build.md).

For the BME280 path, enable I2C and use:

```bash
python -m pip install '.[sensor,x402]'
export SENSOR_BACKEND=bme280
export I2C_ADDRESS=0x76
python -m x402_temperature_server
```

## x402 Production Mode

Set these environment variables on the Pi or hosting service:

```bash
ENABLE_X402=true
X402_PRICE_USD=0.001
X402_NETWORK=base
PAY_TO_EVM_ADDRESS=0xYourReceivingWallet
CDP_API_KEY_ID=...
CDP_API_KEY_SECRET=...
```

With `ENABLE_X402=true`, `GET /temperature` is protected by x402 payment middleware. An unpaid buyer receives a `402 Payment Required` response; a paid buyer receives the JSON reading.

Keep `GET /health` and `GET /.well-known/x402-temperature.json` free so buyer agents can inspect the service before paying.

## Bazaar Discovery

After deployment behind public HTTPS:

1. Confirm the unpaid route returns `402`.
2. Confirm a paid request returns the JSON reading.
3. Validate the endpoint with Coinbase's x402 validation endpoint.
4. Submit the public URL to discovery shelves such as Bazaar.
5. Make your own first paid call and publish the receipt.

The station should advertise a short TTL. A temperature reading is valuable for minutes, not days.

## Tests

```bash
python -m pytest
```

Current tests cover:

- health endpoint
- paid-resource payload shape in mock mode
- rounded coordinates for privacy
- free discovery manifest

## Files

- `src/x402_temperature_server/app.py` - FastAPI app and routes
- `src/x402_temperature_server/sensors.py` - mock, BME280, and DS18B20 sensor backends
- `src/x402_temperature_server/payment.py` - optional x402 middleware installation
- `tests/test_app.py` - offline tests
- `samples/` - representative paid and unpaid output
- `systemd/` - Raspberry Pi service unit

