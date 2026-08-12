from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from glob import glob
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class SensorReading:
    celsius: float
    humidity: float | None = None
    pressure_hpa: float | None = None


class TemperatureSensor:
    def read(self) -> SensorReading:
        raise NotImplementedError


class MockSensor(TemperatureSensor):
    def read(self) -> SensorReading:
        return SensorReading(celsius=21.42, humidity=48.3, pressure_hpa=1013.2)


class Bme280Sensor(TemperatureSensor):
    def __init__(self, address: int = 0x76):
        import board
        import adafruit_bme280.basic as bme280

        i2c = board.I2C()
        self._sensor = bme280.Adafruit_BME280_I2C(i2c, address=address)

    def read(self) -> SensorReading:
        return SensorReading(
            celsius=float(self._sensor.temperature),
            humidity=float(self._sensor.relative_humidity),
            pressure_hpa=float(self._sensor.pressure),
        )


class Ds18b20Sensor(TemperatureSensor):
    def __init__(self, device_glob: str):
        matches = glob(device_glob)
        if not matches:
            raise RuntimeError(f"No DS18B20 device matched {device_glob}")
        self._device = Path(matches[0])

    def read(self) -> SensorReading:
        text = self._device.read_text()
        if "YES" not in text.splitlines()[0]:
            raise RuntimeError("DS18B20 CRC check failed")
        marker = "t="
        raw = text[text.rfind(marker) + len(marker) :].strip()
        return SensorReading(celsius=float(raw) / 1000.0)


def build_sensor(settings: Settings) -> TemperatureSensor:
    backend = settings.sensor_backend.lower()
    if backend == "mock":
        return MockSensor()
    if backend == "bme280":
        return Bme280Sensor(settings.i2c_address)
    if backend == "ds18b20":
        return Ds18b20Sensor(settings.ds18b20_device_glob)
    raise ValueError(f"Unknown SENSOR_BACKEND={settings.sensor_backend!r}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

