# Field Design Recommendations

This file captures the recommendations folded into the public build packet and the choices intentionally left out of the first implementation.

## Recommended Build Sequence

1. Build the wired Raspberry Pi Zero 2 W + BME280 prototype.
2. Verify local readings with the simulated sensor and then with the real BME280.
3. Run the cloud collector on a cheap VPS and have the Pi post readings to it.
4. Put the x402 payment layer in front of the cloud collector's latest-reading endpoint.
5. Add the self-contained Pi seller as a second reference design.
6. Move outdoors only after the indoor wired path and collector path are stable.
7. Add solar/battery power and track uptime before calling it a field station.

## Accepted Recommendations

### Prefer Cloud Collector For The Public Endpoint

The cloud collector is the recommended public seller design because it can stay online when the Pi, home Wi-Fi, or local power has a brief outage. It also lets many sensor nodes share one x402 seller service.

Accepted implementation:

- `POST /sensor-readings` stores the latest reading per station when `ENABLE_CLOUD_COLLECTOR=true`.
- `GET /temperature/latest` returns the latest stored reading.
- The ingest path accepts optional battery fields for solar deployments.
- The ingest path rejects impossible values and readings older than `INGEST_MAX_AGE_SECONDS`.
- The response includes `age_seconds` and `stale` so buyer agents can decide whether the data is useful.

### Keep The Pi Seller As The Edge Reference

The self-contained Pi seller is still valuable because it demonstrates a small physical device selling its own measurement. It is less reliable, so it should be the second design rather than the first production design.

Accepted implementation:

- The direct `/temperature` route remains the live local sensor path.
- The docs describe a public HTTPS route into a Pi-hosted x402 proxy.
- The recommended payment layer remains a thin Node/Express Circle Gateway proxy in front of the Python sensor service.
- The local proxy can run in `mock` mode for offline 402/paid-200 tests or `circle` mode for real Gateway settlement.

### Simulate The Sensor Until Hardware Arrives

The first software demo should not wait on the physical BME280.

Accepted implementation:

- `SENSOR_BACKEND=simulated` is the default.
- The simulated backend produces a daily temperature curve with small configurable noise.
- The deterministic `mock` backend remains available for unit tests.

### Publish Freshness Metadata

Buyer agents should not have to guess whether a paid temperature reading is current.

Accepted implementation:

- Live readings include `age_seconds: 0` and `stale: false`.
- Cloud collector readings compute `age_seconds` from `read_at`.
- Cloud collector readings set `stale` when the reading is older than `READING_TTL_SECONDS`.

### Keep Solar As A Field Upgrade

Solar is important for the outdoor story, but it should not be in the critical path for the first bench build.

Accepted implementation:

- The recommended V1 field kit is Voltaic V75 + 10 W ETFE panel.
- The solar docs size for about 43 Wh/day conservative draw.
- Optional `battery_percent` and `battery_voltage` fields are supported in collector payloads.

## Deferred Recommendations

### Durable Cloud Storage

The included collector uses in-memory storage so it remains easy to run and understand. Production should use SQLite, Postgres, Redis, or a small JSON-backed store so readings survive process restarts.

### Real Paid Circle Gateway Buyer Test

The repo includes the Node/Express Gateway proxy and verifies its local payment contract in mock mode. The next deferred step is a real buyer-wallet estimate and paid call against `X402_GATEWAY_MODE=circle`, after Darryl explicitly approves the amount, seller address, chain/network, and public URL.

### Battery Telemetry Hardware

The response schema supports battery status, but the first hardware order does not include a current/voltage sensor or battery API integration. Add that after the Voltaic kit is installed and the station is running outdoors.

### Multi-Station Management UI

The cloud collector route accepts station ids, which is enough for the reference design. A dashboard, station registry, and per-station API keys can come later.

## Rejected For V1

- Publishing exact latitude and longitude. The repo rounds coordinates by default.
- Requiring public inbound access to the Pi for the primary design.
- Depending on solar power before the wired prototype is verified.
- Making the BME280 sit in direct sun as the outdoor temperature source.
