from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from .config import Settings
from .payment import install_x402
from .sensors import (
    TemperatureSensor,
    build_sensor,
    read_cpu_temperature_celsius,
    read_system_uptime_seconds,
    utc_now_iso,
)


class TemperatureResponse(BaseModel):
    station: str
    location: str
    celsius: float
    fahrenheit: float
    humidity: float | None = None
    pressure_hpa: float | None = None
    read_at: str
    ttl_seconds: int
    age_seconds: int = Field(description="Age of this reading when returned.")
    stale: bool = Field(description="True when the reading is older than the freshness policy.")
    lat: float = Field(description="Rounded latitude. Do not publish exact home coordinates.")
    lon: float = Field(description="Rounded longitude. Do not publish exact home coordinates.")
    battery_percent: float | None = None
    battery_voltage: float | None = None
    device_cpu_celsius: float | None = None
    device_cpu_fahrenheit: float | None = None


class SensorReadingIngest(BaseModel):
    station: str
    celsius: float
    humidity: float | None = None
    pressure_hpa: float | None = None
    read_at: str
    battery_percent: float | None = None
    battery_voltage: float | None = None
    device_cpu_celsius: float | None = None


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="read_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(read_at: str) -> int:
    return max(0, int((datetime.now(timezone.utc) - _parse_utc(read_at)).total_seconds()))


def _validate_reading(reading: SensorReadingIngest) -> None:
    if not -80 <= reading.celsius <= 80:
        raise HTTPException(status_code=422, detail="celsius is outside expected environmental range")
    if reading.humidity is not None and not 0 <= reading.humidity <= 100:
        raise HTTPException(status_code=422, detail="humidity must be between 0 and 100")
    if reading.pressure_hpa is not None and not 800 <= reading.pressure_hpa <= 1200:
        raise HTTPException(status_code=422, detail="pressure_hpa is outside expected environmental range")
    if reading.device_cpu_celsius is not None and not -20 <= reading.device_cpu_celsius <= 120:
        raise HTTPException(status_code=422, detail="device_cpu_celsius is outside expected device range")


def _cpu_fahrenheit(celsius: float | None) -> float | None:
    if celsius is None:
        return None
    return round((celsius * 9 / 5) + 32, 2)


def _fresh_power_status(settings: Settings) -> dict[str, object] | None:
    status_path = Path(settings.power_status_file).expanduser()
    if not status_path.exists():
        return None
    try:
        status = json.loads(status_path.read_text())
        timestamp = str(status["timestamp"])
    except (OSError, ValueError, KeyError, TypeError):
        return None

    age = _age_seconds(timestamp)
    if age > settings.power_status_max_age_seconds:
        return None
    status["age_seconds"] = age
    return status


def _station_health(settings: Settings) -> dict[str, object]:
    cpu_celsius = read_cpu_temperature_celsius()
    uptime_seconds = read_system_uptime_seconds()
    measured_power = _fresh_power_status(settings)
    power = {
        "source": settings.power_source_label,
        "measurement": "estimated",
        "estimated_watts": round(settings.estimated_power_watts, 2),
        "estimated_wh_per_day": round(settings.estimated_power_watts * 24, 1),
        "measured_watts": None,
        "battery_percent": None,
        "battery_voltage": None,
    }
    if measured_power is not None:
        voltage = measured_power.get("voltage_v")
        current = measured_power.get("current_ma")
        measured_watts = measured_power.get("power_mw")
        power.update(
            {
                "source": measured_power.get("source", "ina219"),
                "measurement": "measured",
                "measured_watts": None if measured_watts is None else round(float(measured_watts) / 1000, 3),
                "battery_voltage": voltage,
                "battery_percent": measured_power.get("battery_percent"),
                "current_ma": current,
                "age_seconds": measured_power.get("age_seconds"),
                "shutdown_voltage": measured_power.get("shutdown_voltage"),
                "low_readings": measured_power.get("low_readings"),
            }
        )
    return {
        "uptime_seconds": uptime_seconds,
        "device_cpu_celsius": None if cpu_celsius is None else round(cpu_celsius, 2),
        "device_cpu_fahrenheit": _cpu_fahrenheit(cpu_celsius),
        "power": power,
    }


def _validate_reading_age(read_at: datetime, max_age_seconds: int) -> None:
    age = int((datetime.now(timezone.utc) - read_at).total_seconds())
    if age > max_age_seconds:
        raise HTTPException(status_code=422, detail="reading is too old to ingest")
    if age < -60:
        raise HTTPException(status_code=422, detail="reading timestamp is too far in the future")


def _paid_endpoint(settings: Settings) -> str:
    return "/temperature/latest" if settings.enable_cloud_collector else "/temperature"


def _paid_endpoint_label(settings: Settings) -> str:
    return f"GET {_paid_endpoint(settings)}"


def _install_openapi_metadata(app: FastAPI, settings: Settings) -> None:
    paid_path = _paid_endpoint(settings)

    def custom_openapi() -> dict[str, object]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        info = schema.setdefault("info", {})
        info["x-guidance"] = (
            "Use this service when an agent needs a fresh hyperlocal temperature reading. "
            "The edge architecture sells GET /temperature directly from the sensor service. "
            "The cloud architecture sells GET /temperature/latest from the latest authenticated station post. "
            "Check read_at, age_seconds, ttl_seconds, and stale before relying on the value."
        )
        paid_operation = schema.get("paths", {}).get(paid_path, {}).get("get")
        if paid_operation is not None:
            paid_operation["x-payment-info"] = {
                "price": {"amount": settings.x402_price_usd, "currency": "USD"},
                "protocols": [
                    {
                        "name": "x402",
                        "network": settings.x402_network,
                        "asset": "USDC",
                        "sellerAddress": settings.pay_to_evm_address or "configured-at-proxy",
                    }
                ],
            }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi


def _payment_required_body(settings: Settings) -> dict[str, object]:
    paid_path = _paid_endpoint(settings)
    return {
        "x402Version": 2,
        "resource": {
            "method": "GET",
            "path": paid_path,
            "description": (
                "Latest posted simulated temperature reading from the cloud collector."
                if settings.enable_cloud_collector
                else "Live simulated temperature reading from the edge sensor."
            ),
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": settings.x402_network,
                "asset": "USDC",
                "amount": settings.x402_price_usd,
                "payTo": settings.pay_to_evm_address or "configured-at-proxy",
            }
        ],
    }


def _demo_page(settings: Settings) -> str:
    paid_path = _paid_endpoint(settings)
    architecture = "Cloud collector" if settings.enable_cloud_collector else "Self-contained edge"
    public_lat = round(settings.latitude, 4)
    public_lon = round(settings.longitude, 4)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>x402 Temperature Server Demo</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.45; max-width: 980px; }}
    button {{ margin: 0.25rem 0.5rem 0.25rem 0; padding: 0.55rem 0.75rem; }}
    pre {{ background: #111827; color: #f9fafb; padding: 1rem; overflow: auto; border-radius: 6px; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Danville x402 Temperature Server</h1>
  <p>
    This paid endpoint serves temperature data for Danville, California.
    The public location reference is Sycamore Valley Park, near
    <code>{public_lat}, {public_lon}</code>; it is intentionally not a private home coordinate.
  </p>
  <p><strong>Architecture:</strong> {architecture}</p>
  <p><strong>Location:</strong> {settings.location_label}</p>
  <p><strong>Paid route:</strong> <code>GET {paid_path}</code></p>
  <p>
    Opening the paid route directly should return <code>402 Payment Required</code>.
    Click the mock-paid button to send the local <code>x-payment: test-paid</code> header and see the simulated payload.
  </p>
  <button onclick="callEndpoint('/health')">Health</button>
  <button onclick="callEndpoint('/.well-known/x402-temperature.json')">Manifest</button>
  <button onclick="callEndpoint('{paid_path}')">Unpaid 402</button>
  <button onclick="callEndpoint('{paid_path}', {{'x-payment': 'test-paid'}})">Mock-Paid 200</button>
  <pre id="output">Click a button to run a request.</pre>
  <script>
    async function callEndpoint(path, headers = {{}}, timeoutMs = 8000) {{
      const output = document.getElementById('output');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      output.textContent = 'Loading ' + path + ' ...';
      try {{
        const response = await fetch(path, {{
          cache: 'no-store',
          headers,
          signal: controller.signal
        }});
        const text = await response.text();
        let body = text;
        try {{ body = JSON.stringify(JSON.parse(text), null, 2); }} catch (_) {{}}
        const challenge = response.headers.get('payment-required');
        output.textContent =
          'URL: ' + location.origin + path + '\\n' +
          'Status: ' + response.status + ' ' + response.statusText + '\\n' +
          (challenge ? 'payment-required: ' + challenge + '\\n' : '') +
          '\\n' + body;
      }} catch (error) {{
        output.textContent =
          'Request failed for ' + location.origin + path + '\\n\\n' +
          (error.name === 'AbortError'
            ? 'Timed out after ' + timeoutMs + ' ms. Confirm this browser is on the same LAN as x402host and try a hard refresh.'
            : String(error));
      }} finally {{
        clearTimeout(timer);
      }}
    }}
  </script>
</body>
</html>"""


def _simple_page(settings: Settings) -> str:
    paid_path = _paid_endpoint(settings)
    architecture = "Cloud collector" if settings.enable_cloud_collector else "Self-contained edge"
    paid_url = paid_path
    public_lat = round(settings.latitude, 4)
    public_lon = round(settings.longitude, 4)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>x402 Temperature Server Simple View</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; max-width: 760px; }}
    a {{ display: block; margin: 0.5rem 0; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Danville x402 Temperature Server Simple View</h1>
  <p>This page is intentionally plain HTML with no JavaScript.</p>
  <p>This endpoint represents Danville, California temperature data using Sycamore Valley Park as the public coordinate reference: <code>{public_lat}, {public_lon}</code>.</p>
  <p><strong>Architecture:</strong> {architecture}</p>
  <p><strong>Location:</strong> {settings.location_label}</p>
  <p><strong>Paid route:</strong> <code>GET {paid_path}</code></p>
  <a href="/health">Open health JSON</a>
  <a href="/.well-known/x402-temperature.json">Open discovery manifest JSON</a>
  <a href="{paid_url}">Open paid route directly. A normal browser should see a 402 challenge.</a>
  <a href="/demo">Open JavaScript demo page</a>
</body>
</html>"""


def _install_mock_x402(app: FastAPI, settings: Settings) -> None:
    paid_path = _paid_endpoint(settings)

    @app.middleware("http")
    async def mock_x402_gate(request: Request, call_next):
        if request.method == "GET" and request.url.path == paid_path:
            payment = request.headers.get("x-payment") or request.headers.get("payment")
            if payment != "test-paid":
                body = _payment_required_body(settings)
                return JSONResponse(
                    status_code=402,
                    content=body,
                    headers={"payment-required": base64.b64encode(json.dumps(body).encode()).decode()},
                )
            response = await call_next(request)
            response.headers["x-payment-verified"] = "true"
            return response
        return await call_next(request)


def create_app(settings: Settings | None = None, sensor: TemperatureSensor | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    sensor = sensor or build_sensor(settings)

    app = FastAPI(
        title="x402 Temperature Server",
        version="0.1.0",
        description="Sell live Raspberry Pi temperature readings with x402.",
    )

    app.state.latest_readings = {}
    if settings.enable_cloud_collector and settings.sensor_backend.lower() in {"mock", "simulated"}:
        seed = sensor.read()
        app.state.latest_readings[settings.station_id] = SensorReadingIngest(
            station=settings.station_id,
            celsius=seed.celsius,
            humidity=seed.humidity,
            pressure_hpa=seed.pressure_hpa,
            read_at=utc_now_iso(),
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(_demo_page(settings), headers={"Cache-Control": "no-store"})

    @app.get("/demo", response_class=HTMLResponse)
    def demo() -> HTMLResponse:
        return HTMLResponse(_demo_page(settings), headers={"Cache-Control": "no-store"})

    @app.get("/simple", response_class=HTMLResponse)
    def simple() -> HTMLResponse:
        return HTMLResponse(_simple_page(settings), headers={"Cache-Control": "no-store"})

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "station": settings.station_id,
            "paid_route": settings.enable_x402 or settings.enable_mock_x402,
            "x402_mode": "mock" if settings.enable_mock_x402 else ("direct" if settings.enable_x402 else "off"),
            "collector": settings.enable_cloud_collector,
            "station_health": _station_health(settings),
        }

    @app.get("/temperature", response_model=TemperatureResponse)
    def temperature() -> TemperatureResponse:
        reading = sensor.read()
        celsius = round(reading.celsius, 2)
        cpu_celsius = read_cpu_temperature_celsius()
        rounded_cpu_celsius = None if cpu_celsius is None else round(cpu_celsius, 2)
        return TemperatureResponse(
            station=settings.station_id,
            location=settings.location_label,
            celsius=celsius,
            fahrenheit=round((celsius * 9 / 5) + 32, 2),
            humidity=None if reading.humidity is None else round(reading.humidity, 1),
            pressure_hpa=None if reading.pressure_hpa is None else round(reading.pressure_hpa, 1),
            read_at=utc_now_iso(),
            ttl_seconds=settings.reading_ttl_seconds,
            age_seconds=0,
            stale=False,
            lat=round(settings.latitude, 2),
            lon=round(settings.longitude, 2),
            device_cpu_celsius=rounded_cpu_celsius,
            device_cpu_fahrenheit=_cpu_fahrenheit(rounded_cpu_celsius),
        )

    if settings.enable_cloud_collector:

        @app.post("/sensor-readings")
        def ingest_reading(
            reading: SensorReadingIngest,
            x_station_token: str | None = Header(default=None),
        ) -> dict[str, str | bool]:
            if settings.station_ingest_token and x_station_token != settings.station_ingest_token:
                raise HTTPException(status_code=401, detail="invalid station token")
            _validate_reading(reading)
            read_at = _parse_utc(reading.read_at)
            _validate_reading_age(read_at, settings.ingest_max_age_seconds)
            app.state.latest_readings[reading.station] = reading
            return {"ok": True, "station": reading.station, "stored": True}

        @app.get("/temperature/latest", response_model=TemperatureResponse)
        def latest_temperature(station: str | None = Query(default=None)) -> TemperatureResponse:
            station_id = station or settings.station_id
            reading = app.state.latest_readings.get(station_id)
            if reading is None:
                raise HTTPException(status_code=404, detail="no reading stored for station")
            age = _age_seconds(reading.read_at)
            celsius = round(reading.celsius, 2)
            return TemperatureResponse(
                station=reading.station,
                location=settings.location_label,
                celsius=celsius,
                fahrenheit=round((celsius * 9 / 5) + 32, 2),
                humidity=None if reading.humidity is None else round(reading.humidity, 1),
                pressure_hpa=None if reading.pressure_hpa is None else round(reading.pressure_hpa, 1),
                read_at=reading.read_at,
                ttl_seconds=settings.reading_ttl_seconds,
                age_seconds=age,
                stale=age > settings.reading_ttl_seconds,
                lat=round(settings.latitude, 2),
                lon=round(settings.longitude, 2),
                battery_percent=reading.battery_percent,
                battery_voltage=reading.battery_voltage,
                device_cpu_celsius=None if reading.device_cpu_celsius is None else round(reading.device_cpu_celsius, 2),
                device_cpu_fahrenheit=_cpu_fahrenheit(reading.device_cpu_celsius),
            )

    @app.get("/.well-known/x402-temperature.json")
    def manifest() -> dict[str, object]:
        sample_celsius = round(settings.simulated_base_celsius, 2)
        return {
            "name": "x402 Temperature Server",
            "station": settings.station_id,
            "architecture": "cloud-collector" if settings.enable_cloud_collector else "self-contained-edge",
            "paid_endpoint": _paid_endpoint_label(settings),
            "price_usd": settings.x402_price_usd,
            "network": settings.x402_network,
            "ttl_seconds": settings.reading_ttl_seconds,
            "sample": {
                "station": settings.station_id,
                "location": settings.location_label,
                "celsius": sample_celsius,
                "fahrenheit": round((sample_celsius * 9 / 5) + 32, 2),
                "read_at": "2026-08-12T08:00:00Z",
                "age_seconds": 0,
                "stale": False,
                "lat": round(settings.latitude, 2),
                "lon": round(settings.longitude, 2),
            },
            "station_health": _station_health(settings),
        }

    if settings.enable_mock_x402:
        _install_mock_x402(app, settings)
    elif settings.enable_x402:
        install_x402(app, settings)

    _install_openapi_metadata(app, settings)

    return app


app = create_app()
