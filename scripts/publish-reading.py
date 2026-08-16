#!/usr/bin/env python3
"""Publish the local station reading to a cloud collector.

This is intentionally stdlib-only so it can run from cron on a small Raspberry Pi.
It reads the local simulated or hardware-backed sensor endpoint, then posts the
latest reading to the cloud collector using the station ingest token.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


LOCAL_SENSOR_URL = os.getenv("LOCAL_SENSOR_URL", "http://127.0.0.1:8080/temperature")
CLOUD_INGEST_URL = os.getenv("CLOUD_INGEST_URL", "https://x402-temperature.ngrok.app/sensor-readings")
STATION_INGEST_TOKEN = os.getenv("STATION_INGEST_TOKEN", "")


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
      return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            **headers,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    if not STATION_INGEST_TOKEN:
        print("STATION_INGEST_TOKEN is required", file=sys.stderr)
        return 2

    reading = fetch_json(LOCAL_SENSOR_URL, {"x-payment": "test-paid"})
    payload = {
        "station": reading["station"],
        "celsius": reading["celsius"],
        "humidity": reading.get("humidity"),
        "pressure_hpa": reading.get("pressure_hpa"),
        "read_at": reading["read_at"],
        "battery_percent": reading.get("battery_percent"),
        "battery_voltage": reading.get("battery_voltage"),
        "device_cpu_celsius": reading.get("device_cpu_celsius"),
    }
    result = post_json(
        CLOUD_INGEST_URL,
        payload,
        {"x-station-token": STATION_INGEST_TOKEN},
    )
    print(json.dumps({"published": True, "collector": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {detail}", file=sys.stderr)
        raise SystemExit(1)
