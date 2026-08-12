from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .config import Settings
from .payment import install_x402
from .sensors import TemperatureSensor, build_sensor, utc_now_iso


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


class SensorReadingIngest(BaseModel):
    station: str
    celsius: float
    humidity: float | None = None
    pressure_hpa: float | None = None
    read_at: str
    battery_percent: float | None = None
    battery_voltage: float | None = None


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


def _validate_reading_age(read_at: datetime, max_age_seconds: int) -> None:
    age = int((datetime.now(timezone.utc) - read_at).total_seconds())
    if age > max_age_seconds:
        raise HTTPException(status_code=422, detail="reading is too old to ingest")
    if age < -60:
        raise HTTPException(status_code=422, detail="reading timestamp is too far in the future")


def create_app(settings: Settings | None = None, sensor: TemperatureSensor | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    sensor = sensor or build_sensor(settings)

    app = FastAPI(
        title="x402 Temperature Server",
        version="0.1.0",
        description="Sell live Raspberry Pi temperature readings with x402.",
    )

    app.state.latest_readings = {}

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "ok": True,
            "station": settings.station_id,
            "paid_route": settings.enable_x402,
            "collector": settings.enable_cloud_collector,
        }

    @app.get("/temperature", response_model=TemperatureResponse)
    def temperature() -> TemperatureResponse:
        reading = sensor.read()
        celsius = round(reading.celsius, 2)
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
            )

    @app.get("/.well-known/x402-temperature.json")
    def manifest() -> dict[str, object]:
        return {
            "name": "x402 Temperature Server",
            "station": settings.station_id,
            "paid_endpoint": "GET /temperature",
            "price_usd": settings.x402_price_usd,
            "network": settings.x402_network,
            "ttl_seconds": settings.reading_ttl_seconds,
            "sample": {
                "station": settings.station_id,
                "celsius": 21.42,
                "fahrenheit": 70.56,
                "read_at": "2026-08-12T08:00:00Z",
                "age_seconds": 0,
                "stale": False,
            },
        }

    if settings.enable_x402:
        install_x402(app, settings)

    return app


app = create_app()
