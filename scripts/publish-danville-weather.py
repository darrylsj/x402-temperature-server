#!/usr/bin/env python3
"""Publish the current Danville public weather feed to the cloud collector.

This keeps the cloud demo realistic while the field station has no outdoor
temperature sensor installed yet. It is intentionally stdlib-only for cron on
small hosts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
import urllib.error
import urllib.request


CLOUD_INGEST_URL = os.getenv("CLOUD_INGEST_URL", "https://x402-temperature.ngrok.app/sensor-readings")
STATION_INGEST_TOKEN = os.getenv("STATION_INGEST_TOKEN", "")
NWS_HOURLY_URL = os.getenv(
    "NWS_HOURLY_URL",
    "https://api.weather.gov/gridpoints/MTR/100,104/forecast/hourly",
)
USER_AGENT = os.getenv("NWS_USER_AGENT", "x402-temperature-server/0.1 (darrylsj)")
STATION_ID = os.getenv("STATION_ID", "danville-demo-01")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "accept": "application/geo+json, application/json",
            "user-agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
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
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0


def current_period(payload: dict) -> dict:
    periods = payload.get("properties", {}).get("periods") or []
    if not periods:
        raise RuntimeError("NWS hourly forecast returned no periods")
    return periods[0]


def main() -> int:
    if not STATION_INGEST_TOKEN:
        print("STATION_INGEST_TOKEN is required", file=sys.stderr)
        return 2

    period = current_period(fetch_json(NWS_HOURLY_URL))
    temp_f = float(period["temperature"])
    unit = period.get("temperatureUnit", "F")
    celsius = fahrenheit_to_celsius(temp_f) if unit == "F" else temp_f
    humidity = period.get("relativeHumidity", {}).get("value")

    payload = {
        "station": STATION_ID,
        "celsius": round(celsius, 2),
        "humidity": None if humidity is None else float(humidity),
        "pressure_hpa": None,
        "read_at": utc_now_iso(),
        "battery_percent": None,
        "battery_voltage": None,
        "device_cpu_celsius": None,
    }
    result = post_json(
        CLOUD_INGEST_URL,
        payload,
        {"x-station-token": STATION_INGEST_TOKEN},
    )
    print(
        json.dumps(
            {
                "published": True,
                "source": "nws-hourly-forecast",
                "forecast_start": period.get("startTime"),
                "short_forecast": period.get("shortForecast"),
                "payload": payload,
                "collector": result,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {detail}", file=sys.stderr)
        raise SystemExit(1)
