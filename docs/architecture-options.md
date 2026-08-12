# Architecture Options

This project supports two production designs. They use the same sensor code, but make different reliability and cost trade-offs.

![Cloud collector architecture and self-contained Pi architecture](images/cloud-vs-self-contained-architecture.jpg)

## Option A: Cloud Collector + x402 Seller

In this design the Raspberry Pi is a private sensor node. It reads the BME280 or DS18B20 and periodically posts a signed reading to a small cloud service. The cloud service stores the latest reading and exposes the paid x402 endpoint.

```text
Raspberry Pi sensor node
  -> HTTPS POST /sensor-readings
  -> cheap cloud VPS
  -> x402 protected GET /temperature/latest
  -> buyer agents
```

### Why Use This Design

- The paid endpoint stays online even if the Pi reboots or loses home internet.
- Multiple sensors can post to the same cloud service.
- The x402 seller address, payment middleware, TLS certificate, logs, and marketplace metadata live in one place.
- The Pi can stay behind NAT and does not need inbound firewall rules.
- Cloud uptime is easier to monitor than a home network.

### Downsides

- It adds a monthly hosting cost.
- It adds a sync delay. The buyer receives the latest posted reading, not necessarily a live sensor read at request time.
- It may never be profitable at one-tenth-of-a-cent pricing unless many sensors or buyers share the same cloud service.
- It is less romantically pure than """a tiny computer sells its own weather.""" Terrible for poetry, better for uptime.

### Recommended Cloud Host

Recommended practical host:

- RackNerd 1 GB KVM VPS special, usually around USD 21.99/year when available.
- Typical published spec: 1 vCPU, 1 GB RAM, 20 GB SSD, 3 TB monthly transfer, IPv4 included.
- Effective cost: about USD 1.83/month.

Strict one-dollar target:

- VPS1Dollar advertises VPS plans from USD 1/month with IPv6-first networking and NAT64.
- Use it only if the exact one-dollar target matters more than provider maturity, support depth, and conventional IPv4 simplicity.

Credible slightly-higher fallback:

- IONOS VPS XS is often one of the cheapest mainstream options, but pricing is usually closer to USD 2/month or higher.

Recommendation: use RackNerd for the working reference design. It is cheap enough for the book and less fragile than chasing an exact USD 1/month host.

### Cloud Service Responsibilities

- `POST /sensor-readings`
  - Authenticated by a per-station ingest token.
  - Accepts station id, reading timestamp, temperature, humidity, pressure, and optional battery status.
  - Rejects readings that are too old or have impossible values.

- `GET /temperature/latest`
  - x402-protected.
  - Returns the latest valid reading for a station.
  - Includes `read_at`, `age_seconds`, and `stale` so buyers know whether the reading is fresh.

- `GET /health`
  - Free.
  - Reports service health and latest station age.

- `GET /.well-known/x402-temperature.json`
  - Free.
  - Describes endpoint price, response schema, station ids, and freshness policy.

### Suggested Freshness Policy

```text
Pi post interval: every 60 seconds
Fresh reading: <= 180 seconds old
Stale but returnable: <= 900 seconds old
Expired: > 900 seconds old, return 503 or a stale marker depending on buyer contract
```

For a paid endpoint, the cloud service should be honest when the station is stale. A buyer agent should not pay for yesterday's weather unless it explicitly asked for historical data.

## Option B: Self-Contained Pi Seller

In this design the Raspberry Pi reads the sensor and runs the paid endpoint itself.

```text
Buyer agent
  -> public HTTPS URL
  -> Raspberry Pi x402 endpoint
  -> local sensor read
  -> paid JSON response
```

### Why Use This Design

- It is the cleanest demo: the sensor computer directly sells its own measurement.
- No monthly cloud server is required.
- The paid response can be a truly live reading taken at request time.
- It is a better educational example for edge autonomy.

### Downsides

- Home internet, Wi-Fi, power, and Pi health now define endpoint uptime.
- Public ingress is harder. You need Cloudflare Tunnel, Tailscale Funnel, Caddy with port forwarding, or another HTTPS exposure path.
- A reboot, SD card issue, or local outage takes the paid endpoint offline.
- Running payment middleware on the Pi consumes more memory and creates more moving parts on the edge device.

### Payment Implementation

For the current Circle Gateway Nanopayments seller path, prefer a thin Node/Express proxy even in the self-contained design:

```text
Public HTTPS
  -> Node/Express x402 Gateway middleware on Pi
  -> localhost FastAPI sensor service
```

This keeps the Python sensor service simple while using Circle's current seller middleware for x402 settlement.

## Recommendation

Build both, but sequence them:

1. Build the wired Pi sensor and verify local readings.
2. Add the cloud collector design first for reliable public x402 sales.
3. Add the self-contained Pi seller as the pure edge reference design.
4. Compare uptime, paid-call success rate, and freshness across both.

The cloud option is the stronger production pattern. The self-contained option is the stronger story.
