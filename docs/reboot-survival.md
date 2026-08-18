# Reboot Survival Runbook

This runbook captures the minimum operating setup that keeps the x402
temperature bot alive after Pi and Mac restarts.

The live demo currently has two public surfaces:

| Endpoint | Purpose | Expected unpaid paid-route result |
| --- | --- | --- |
| `https://x402-temperature.ngrok.app` | Cloud/SIM collector route | `GET /temperature/latest` returns `402 Payment Required` |
| `https://x402-temperature-edge.ngrok.app` | Direct edge/Pi route | `GET /temperature` returns `402 Payment Required` |

The free routes should remain reachable without payment:

```bash
curl -fsS -H 'ngrok-skip-browser-warning: true' https://x402-temperature.ngrok.app/health
curl -fsS -H 'ngrok-skip-browser-warning: true' https://x402-temperature-edge.ngrok.app/health
```

## 1. Pi App Autostart

The Pi should run the FastAPI app through systemd, not through a manually
started shell, `screen`, `tmux`, or a user crontab fallback.

Live host assumptions:

```text
Pi host: x402host.local
LAN IP: 10.0.0.24
Service: x402-temperature-server
Repo/app path: /home/james/projects/x402-temperature-server
Local app URL on Pi: http://127.0.0.1:8080
```

Install or refresh the service on the Pi:

```bash
sudo tee /etc/systemd/system/x402-temperature-server.service >/dev/null <<'EOF'
[Unit]
Description=x402 Temperature Server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/james/projects/x402-temperature-server
EnvironmentFile=-/home/james/projects/x402-temperature-server/.env
ExecStart=/home/james/projects/x402-temperature-server/.venv/bin/python -m x402_temperature_server
Restart=always
RestartSec=5
User=james

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable x402-temperature-server
sudo systemctl restart x402-temperature-server
```

Verify:

```bash
systemctl is-enabled x402-temperature-server
systemctl is-active x402-temperature-server
curl -fsS http://127.0.0.1:8080/health
journalctl -u x402-temperature-server -n 80 --no-pager
```

Expected:

```text
enabled
active
```

## 2. Limited Maintenance Sudo

An automation agent should not need broad passwordless sudo. If unattended
maintenance is required, limit it to this service.

Example sudoers rule:

```bash
sudo tee /etc/sudoers.d/99-james-x402-maintenance >/dev/null <<'EOF'
james ALL=(root) NOPASSWD: /usr/bin/systemctl status x402-temperature-server, /usr/bin/systemctl is-active x402-temperature-server, /usr/bin/systemctl is-enabled x402-temperature-server, /usr/bin/systemctl restart x402-temperature-server, /usr/bin/systemctl start x402-temperature-server, /usr/bin/systemctl stop x402-temperature-server, /usr/bin/journalctl -u x402-temperature-server *
EOF
sudo chmod 440 /etc/sudoers.d/99-james-x402-maintenance
sudo visudo -cf /etc/sudoers.d/99-james-x402-maintenance
```

Remove any temporary broad sudoers rule after the service is installed:

```bash
sudo rm -f /etc/sudoers.d/99-james-temp
```

## 3. Remove Crontab App Fallbacks

Once systemd owns the app, remove user-crontab fallbacks that start the
FastAPI process directly. Keep publisher crons that post readings to the
cloud collector.

Inspect:

```bash
crontab -l
```

Remove only direct server-start/self-heal lines containing
`x402_temperature_server` or `x402-temperature-server/.venv/bin/python -m
x402_temperature_server`.

Keep the Danville weather publisher until a real sensor publisher replaces it:

```cron
2 * * * * cd /home/james/projects/x402-temperature-server && set -a && . /home/james/.x402-temperature-cloud.env && set +a && /usr/bin/python3 scripts/publish-danville-weather.py >> /tmp/x402-publish-danville-weather.log 2>&1
```

## 4. Mac Tunnel Autostart

The direct edge path depends on Mac-side autostart for:

```text
com.ngrok.tunnels
com.james.x402-pi-tunnel
com.james.x402-temperature-proxy
```

Verify from the Mac:

```bash
launchctl list | grep -E 'com.ngrok.tunnels|com.james.x402-pi-tunnel|com.james.x402-temperature-proxy'
```

The edge route is:

```text
ngrok public URL
  -> Mac Node x402 proxy on 127.0.0.1:3091
  -> Mac SSH forward on 127.0.0.1:18080
  -> Pi FastAPI app on 127.0.0.1:8080
```

If the Pi app is active but the public edge URL fails, check the LaunchAgents
and the SSH forward before changing the Pi service.

## 5. Daily Health Check

The daily check should verify all layers without making a paid purchase:

```bash
ssh james@10.0.0.24 'sudo -n systemctl is-enabled x402-temperature-server && sudo -n systemctl is-active x402-temperature-server && curl -fsS http://127.0.0.1:8080/health'

curl -fsS -H 'ngrok-skip-browser-warning: true' https://x402-temperature-edge.ngrok.app/health
curl -fsS -H 'ngrok-skip-browser-warning: true' https://x402-temperature.ngrok.app/health

curl -sS -o /tmp/x402-edge-paid.out -w '%{http_code}\n' -H 'ngrok-skip-browser-warning: true' https://x402-temperature-edge.ngrok.app/temperature
curl -sS -o /tmp/x402-cloud-paid.out -w '%{http_code}\n' -H 'ngrok-skip-browser-warning: true' https://x402-temperature.ngrok.app/temperature/latest
```

Expected paid-route HTTP status for both unpaid calls:

```text
402
```

If `systemctl is-active` is not `active`, restart the service once and recheck:

```bash
ssh james@10.0.0.24 'sudo -n systemctl restart x402-temperature-server && sleep 5 && sudo -n systemctl is-active x402-temperature-server && curl -fsS http://127.0.0.1:8080/health'
```

## 6. Reboot Test

Before calling reboot survival done:

1. Reboot the Pi.
2. Wait for Wi-Fi and `network-online.target`.
3. Confirm `x402-temperature-server` is `enabled` and `active`.
4. Confirm Pi local `/health` works.
5. Confirm Mac LaunchAgents are running after a Mac login/restart.
6. Confirm both public `/health` routes work.
7. Confirm both paid routes return unpaid `402`.
8. Confirm no broad temporary sudoers file remains.
9. Confirm no direct app crontab fallback remains.

Do not use paid buyer tests for daily health. Paid tests are separate release
verification and require explicit spend approval.
