from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from glob import glob
import math
import random
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class SensorReading:
    celsius: float
    humidity: float | None = None
    pressure_hpa: float | None = None


def read_cpu_temperature_celsius(path: str = "/sys/class/thermal/thermal_zone0/temp") -> float | None:
    thermal_path = Path(path)
    if not thermal_path.exists():
        return None
    try:
        raw = thermal_path.read_text().strip()
        if not raw:
            return None
        value = float(raw)
    except (OSError, ValueError):
        return None
    return value / 1000.0 if value > 1000 else value


def read_system_uptime_seconds(path: str = "/proc/uptime") -> int | None:
    uptime_path = Path(path)
    if not uptime_path.exists():
        return None
    try:
        raw = uptime_path.read_text().split()[0]
        return int(float(raw))
    except (OSError, ValueError, IndexError):
        return None


class TemperatureSensor:
    def read(self) -> SensorReading:
        raise NotImplementedError


class MockSensor(TemperatureSensor):
    def read(self) -> SensorReading:
        return SensorReading(celsius=21.42, humidity=48.3, pressure_hpa=1013.2)


class SimulatedSensor(TemperatureSensor):
    def __init__(
        self,
        base_celsius: float,
        daily_swing_celsius: float,
        noise_celsius: float,
        humidity: float,
        pressure_hpa: float,
    ):
        self._base_celsius = base_celsius
        self._daily_swing_celsius = daily_swing_celsius
        self._noise_celsius = noise_celsius
        self._humidity = humidity
        self._pressure_hpa = pressure_hpa

    def read(self) -> SensorReading:
        now = datetime.now(timezone.utc)
        seconds_since_midnight = now.hour * 3600 + now.minute * 60 + now.second
        day_fraction = seconds_since_midnight / 86400
        daily_curve = math.sin((day_fraction - 0.25) * math.tau)
        noise = random.uniform(-self._noise_celsius, self._noise_celsius)
        celsius = self._base_celsius + (daily_curve * self._daily_swing_celsius) + noise
        return SensorReading(
            celsius=celsius,
            humidity=self._humidity,
            pressure_hpa=self._pressure_hpa,
        )


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
    if backend == "simulated":
        return SimulatedSensor(
            base_celsius=settings.simulated_base_celsius,
            daily_swing_celsius=settings.simulated_daily_swing_celsius,
            noise_celsius=settings.simulated_noise_celsius,
            humidity=settings.simulated_humidity,
            pressure_hpa=settings.simulated_pressure_hpa,
        )
    if backend == "bme280":
        return Bme280Sensor(settings.i2c_address)
    if backend == "ds18b20":
        return Ds18b20Sensor(settings.ds18b20_device_glob)
    raise ValueError(f"Unknown SENSOR_BACKEND={settings.sensor_backend!r}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
