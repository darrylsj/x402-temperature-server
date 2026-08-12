from __future__ import annotations

from fastapi import FastAPI
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
    lat: float = Field(description="Rounded latitude. Do not publish exact home coordinates.")
    lon: float = Field(description="Rounded longitude. Do not publish exact home coordinates.")


def create_app(settings: Settings | None = None, sensor: TemperatureSensor | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    sensor = sensor or build_sensor(settings)

    app = FastAPI(
        title="x402 Temperature Server",
        version="0.1.0",
        description="Sell live Raspberry Pi temperature readings with x402.",
    )

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"ok": True, "station": settings.station_id, "paid_route": settings.enable_x402}

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
            lat=round(settings.latitude, 2),
            lon=round(settings.longitude, 2),
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
            },
        }

    if settings.enable_x402:
        install_x402(app, settings)

    return app


app = create_app()

