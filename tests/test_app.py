from fastapi.testclient import TestClient

from x402_temperature_server.app import create_app
from x402_temperature_server.config import Settings
from x402_temperature_server.sensors import MockSensor, SimulatedSensor, utc_now_iso


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
    assert response.json() == {
        "ok": True,
        "station": "roof-test-01",
        "paid_route": False,
        "x402_mode": "off",
        "collector": False,
    }


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
    assert payload["age_seconds"] == 0
    assert payload["stale"] is False
    assert payload["read_at"].endswith("Z")


def test_coordinates_are_rounded_for_privacy() -> None:
    payload = client().get("/temperature").json()
    assert payload["lat"] == 37.77
    assert payload["lon"] == -122.42


def test_free_manifest_names_paid_route() -> None:
    payload = client().get("/.well-known/x402-temperature.json").json()
    assert payload["architecture"] == "self-contained-edge"
    assert payload["paid_endpoint"] == "GET /temperature"
    assert payload["price_usd"] == "0.001"


def test_openapi_marks_paid_edge_operation_for_agents() -> None:
    payload = client().get("/openapi.json").json()
    assert payload["info"]["x-guidance"]
    payment_info = payload["paths"]["/temperature"]["get"]["x-payment-info"]
    assert payment_info["price"] == {"amount": "0.001", "currency": "USD"}
    assert payment_info["protocols"][0]["name"] == "x402"


def test_mock_x402_gates_edge_route_without_payment() -> None:
    settings = Settings(enable_mock_x402=True)
    test_client = TestClient(create_app(settings=settings, sensor=MockSensor()))

    unpaid = test_client.get("/temperature")
    assert unpaid.status_code == 402
    assert unpaid.json()["resource"]["path"] == "/temperature"
    assert "payment-required" in unpaid.headers

    paid = test_client.get("/temperature", headers={"x-payment": "test-paid"})
    assert paid.status_code == 200
    assert paid.headers["x-payment-verified"] == "true"
    assert test_client.get("/health").json()["x402_mode"] == "mock"


def test_simulated_sensor_payload_is_environmental() -> None:
    settings = Settings(
        sensor_backend="simulated",
        station_id="roof-test-01",
        simulated_base_celsius=21.4,
        simulated_daily_swing_celsius=0,
        simulated_noise_celsius=0,
        simulated_humidity=49.5,
        simulated_pressure_hpa=1012.6,
    )
    test_client = TestClient(create_app(settings=settings, sensor=SimulatedSensor(21.4, 0, 0, 49.5, 1012.6)))
    payload = test_client.get("/temperature").json()
    assert payload["celsius"] == 21.4
    assert payload["fahrenheit"] == 70.52
    assert payload["humidity"] == 49.5
    assert payload["pressure_hpa"] == 1012.6


def test_cloud_collector_ingest_and_latest() -> None:
    settings = Settings(
        sensor_backend="mock",
        station_id="roof-test-01",
        location_label="Test neighborhood",
        latitude=37.7749295,
        longitude=-122.4194155,
        enable_cloud_collector=True,
        station_ingest_token="secret",
    )
    test_client = TestClient(create_app(settings=settings, sensor=MockSensor()))

    reading = {
        "station": "roof-test-01",
        "celsius": 19.5,
        "humidity": 52.25,
        "pressure_hpa": 1011.74,
        "read_at": utc_now_iso(),
        "battery_percent": 84.0,
        "battery_voltage": 5.08,
    }
    ingest = test_client.post("/sensor-readings", json=reading, headers={"X-Station-Token": "secret"})
    assert ingest.status_code == 200

    latest = test_client.get("/temperature/latest").json()
    assert latest["station"] == "roof-test-01"
    assert latest["celsius"] == 19.5
    assert latest["fahrenheit"] == 67.1
    assert latest["humidity"] == 52.2
    assert latest["pressure_hpa"] == 1011.7
    assert latest["battery_percent"] == 84.0
    assert latest["battery_voltage"] == 5.08
    assert latest["age_seconds"] >= 0
    assert latest["stale"] is False

    manifest = test_client.get("/.well-known/x402-temperature.json").json()
    assert manifest["architecture"] == "cloud-collector"
    assert manifest["paid_endpoint"] == "GET /temperature/latest"
    openapi = test_client.get("/openapi.json").json()
    assert "x-payment-info" in openapi["paths"]["/temperature/latest"]["get"]


def test_mock_x402_gates_cloud_route_without_payment() -> None:
    settings = Settings(enable_cloud_collector=True, enable_mock_x402=True, station_ingest_token="secret")
    test_client = TestClient(create_app(settings=settings, sensor=MockSensor()))
    unpaid = test_client.get("/temperature/latest")
    assert unpaid.status_code == 402
    assert unpaid.json()["resource"]["path"] == "/temperature/latest"


def test_cloud_collector_rejects_bad_token() -> None:
    settings = Settings(enable_cloud_collector=True, station_ingest_token="secret")
    test_client = TestClient(create_app(settings=settings, sensor=MockSensor()))
    response = test_client.post(
        "/sensor-readings",
        json={"station": "roof-test-01", "celsius": 19.5, "read_at": "2026-08-12T08:00:00Z"},
        headers={"X-Station-Token": "wrong"},
    )
    assert response.status_code == 401


def test_cloud_collector_rejects_old_reading() -> None:
    settings = Settings(enable_cloud_collector=True, station_ingest_token="secret", ingest_max_age_seconds=60)
    test_client = TestClient(create_app(settings=settings, sensor=MockSensor()))
    response = test_client.post(
        "/sensor-readings",
        json={"station": "roof-test-01", "celsius": 19.5, "read_at": "2026-08-12T08:00:00Z"},
        headers={"X-Station-Token": "secret"},
    )
    assert response.status_code == 422
