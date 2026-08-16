# Public ngrok Demo

Use ngrok when the Pi is on a private home LAN but buyer agents need a public HTTPS URL.

This is the quickest demo path. It avoids router port-forwarding, public DNS, and home firewall changes. For a cloud-connected seller, run the collector/proxy on a public server and point the stable ngrok endpoint at that server instead of at the home LAN.

The current public sample endpoint is:

```text
https://x402-temperature.ngrok.app
```

Current public demo URLs:

```text
Cloud collector on SIM: https://x402-temperature.ngrok.app/demo
Direct edge/Pi path:    https://x402-temperature-edge.ngrok.app/demo
```

Current live deployment:

```text
x402host Raspberry Pi on the home LAN
  -> publishes simulated Danville readings every minute
  -> https://x402-temperature.ngrok.app/sensor-readings
  -> SIM cloud server collector
  -> paid cloud route: GET /temperature/latest
```

The SIM cloud server keeps the Python collector and Node Gateway proxy bound to localhost; ngrok provides the public HTTPS entrypoint.

For real seller testing, this URL should point at the Node/Express Circle Gateway proxy, not directly at the Python mock gate:

```text
ngrok HTTPS
  -> local proxy on :3090
  -> SSH forward on :18080
  -> Pi Python temperature service on x402host:8080
```

For the cloud collector architecture, the same stable endpoint fronts the cloud server proxy:

```text
ngrok HTTPS
  -> ngrok agent on the cloud server
  -> Node/Express Circle Gateway proxy on 127.0.0.1:3090
  -> Python cloud collector on 127.0.0.1:8091
```

For the direct edge architecture, a separate public endpoint fronts the edge proxy:

```text
ngrok HTTPS at https://x402-temperature-edge.ngrok.app
  -> ngrok agent on the Mac
  -> Node/Express Circle Gateway proxy on 127.0.0.1:3091
  -> SSH forward on 127.0.0.1:18080
  -> x402host Pi edge service on 127.0.0.1:8080
```

The Pi publishes readings to the cloud collector through the public endpoint:

```bash
STATION_INGEST_TOKEN=replace-with-random-token \
CLOUD_INGEST_URL=https://x402-temperature.ngrok.app/sensor-readings \
LOCAL_SENSOR_URL=http://127.0.0.1:8080/temperature \
python3 scripts/publish-reading.py
```

## Recommended Demo Topology

```text
buyer agent
  -> public ngrok HTTPS URL
  -> ngrok agent on the Mac or Pi
  -> x402 temperature server on the Pi
```

If ngrok runs directly on the Pi, point the tunnel at the local service:

```bash
ngrok http --url https://x402-temperature.ngrok.app http://127.0.0.1:8080
```

If ngrok is already running on another machine on the LAN, such as a Mac that also hosts other tunnels, create a local SSH forward from that machine to the Pi:

```bash
ssh -f \
  -o BatchMode=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -N \
  -L 0.0.0.0:18080:127.0.0.1:8080 \
  james@10.0.0.24
```

Then create a separate ngrok tunnel that forwards to the local port-forward:

```bash
curl -X POST http://127.0.0.1:4040/api/tunnels \
  -H 'Content-Type: application/json' \
  -d '{"name":"x402-temperature","addr":"http://127.0.0.1:18080","proto":"http","hostname":"x402-temperature.ngrok.app"}'
```

To make the tunnel survive Mac restarts, add the same public URL to the ngrok config:

```yaml
tunnels:
  x402-temperature:
    addr: 18080
    proto: http
    url: https://x402-temperature.ngrok.app
```

The SSH forward also needs to survive restarts. On macOS, use a LaunchAgent that runs:

```bash
ssh \
  -o BatchMode=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -N \
  -L 0.0.0.0:18080:127.0.0.1:8080 \
  james@10.0.0.24
```

## Public Seller Smoke Test

Set the public URL ngrok returns:

```bash
URL='https://x402-temperature.ngrok.app'
```

Health should return `200`:

```bash
curl -H 'ngrok-skip-browser-warning: true' "$URL/health"
```

The unpaid paid route should return `402 Payment Required` with Circle Gateway payment requirements:

```bash
curl -i -H 'ngrok-skip-browser-warning: true' "$URL/temperature/latest"
```

Circle's read-only inspect command should report the endpoint as payable:

```bash
circle services inspect "$URL/temperature/latest" --output json
```

For the confirmed paid buyer test flow, see [Paid Buyer Test](paid-buyer-test.md). The first successful 50-call run used Polygon Amoy testnet Gateway balance and completed 50 paid purchases with zero failures.

The `ngrok-skip-browser-warning` header is useful for automated agents and scripts that should bypass ngrok's browser interstitial. The `x-payment: test-paid` header only works in local mock mode; it is not a real payment.

## Router Port Forwarding Alternative

Traditional port forwarding also works:

```text
public router IP:443
  -> Raspberry Pi 10.0.0.24:8080
```

Do not expose the Pi directly on plain HTTP for a real seller endpoint. Put TLS, authentication for admin surfaces, and the x402 Gateway proxy in front of the paid route.

## Production Buyer Flow

The mock Python x402 mode proves the HTTP contract but does not settle USDC. A real outside-LAN purchase needs:

1. A stable public HTTPS URL.
2. The Node/Express Circle Gateway proxy in front of the Python sensor service.
3. A configured seller receive address.
4. A real unpaid `402` challenge with current accepted networks and price.
5. A buyer-wallet estimate before any paid test call.

Confirmed USDC payments are irreversible. Keep first paid tests on testnet where possible, or ask for explicit approval before moving real funds. Polygon Amoy is the fastest verified testnet buyer path for demos. Base Sepolia also works, but Gateway balance does not become available until Circle's required finality window has passed; always poll `circle gateway balance` before paying.
