from fastapi.testclient import TestClient

from x402_temperature_server.app import create_app
from x402_temperature_server.config import Settings
from x402_temperature_server.sensors import MockSensor


def client() -> TestClient:
    settings = Settings(
        sensor_backend="mock",
        station_id="roof-test-01",
        location_label="Test neighborhood",
        latitude=37.7749295,
        longitude=-122.4194155,
        enable_x402=False,
    )
    return TestClient(create_app(settings=settings, sensor=MockSensor()))


def test_health() -> None:
    response = client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "station": "roof-test-01", "paid_route": False}


def test_temperature_payload() -> None:
    response = client().get("/temperature")
    assert response.status_code == 200
    payload = response.json()
    assert payload["station"] == "roof-test-01"
    assert payload["celsius"] == 21.42
    assert payload["fahrenheit"] == 70.56
    assert payload["humidity"] == 48.3
    assert payload["pressure_hpa"] == 1013.2
    assert payload["ttl_seconds"] == 60
    assert payload["read_at"].endswith("Z")


def test_coordinates_are_rounded_for_privacy() -> None:
    payload = client().get("/temperature").json()
    assert payload["lat"] == 37.77
    assert payload["lon"] == -122.42


def test_free_manifest_names_paid_route() -> None:
    payload = client().get("/.well-known/x402-temperature.json").json()
    assert payload["paid_endpoint"] == "GET /temperature"
    assert payload["price_usd"] == "0.001"

