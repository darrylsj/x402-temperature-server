from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw in (None, "") else float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in (None, "") else int(raw)


@dataclass(frozen=True)
class Settings:
    sensor_backend: str = "simulated"
    station_id: str = "danville-demo-01"
    location_label: str = "Danville, CA - Sycamore Valley Park reference"
    latitude: float = 37.8074706
    longitude: float = -121.9464792
    reading_ttl_seconds: int = 60
    simulated_base_celsius: float = 22.22
    simulated_daily_swing_celsius: float = 0.0
    simulated_noise_celsius: float = 0.15
    simulated_humidity: float = 54.0
    simulated_pressure_hpa: float = 1017.0
    i2c_address: int = 0x76
    ds18b20_device_glob: str = "/sys/bus/w1/devices/28-*/w1_slave"
    enable_x402: bool = False
    enable_mock_x402: bool = False
    x402_price_usd: str = "0.001"
    x402_network: str = "base"
    pay_to_evm_address: str = ""
    enable_cloud_collector: bool = False
    station_ingest_token: str = ""
    ingest_max_age_seconds: int = 900
    power_source_label: str = "usb-wall-power"
    estimated_power_watts: float = 1.5
    power_status_file: str = "~/.x402-temperature-power.json"
    power_status_max_age_seconds: int = 180

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            sensor_backend=os.getenv("SENSOR_BACKEND", "simulated"),
            station_id=os.getenv("STATION_ID", "danville-demo-01"),
            location_label=os.getenv("LOCATION_LABEL", "Danville, CA - Sycamore Valley Park reference"),
            latitude=_float("LATITUDE", 37.8074706),
            longitude=_float("LONGITUDE", -121.9464792),
            reading_ttl_seconds=_int("READING_TTL_SECONDS", 60),
            simulated_base_celsius=_float("SIMULATED_BASE_CELSIUS", 22.22),
            simulated_daily_swing_celsius=_float("SIMULATED_DAILY_SWING_CELSIUS", 0.0),
            simulated_noise_celsius=_float("SIMULATED_NOISE_CELSIUS", 0.15),
            simulated_humidity=_float("SIMULATED_HUMIDITY", 54.0),
            simulated_pressure_hpa=_float("SIMULATED_PRESSURE_HPA", 1017.0),
            i2c_address=int(os.getenv("I2C_ADDRESS", "0x76"), 0),
            ds18b20_device_glob=os.getenv("DS18B20_DEVICE_GLOB", "/sys/bus/w1/devices/28-*/w1_slave"),
            enable_x402=_bool(os.getenv("ENABLE_X402"), False),
            enable_mock_x402=_bool(os.getenv("ENABLE_MOCK_X402"), False),
            x402_price_usd=os.getenv("X402_PRICE_USD", "0.001"),
            x402_network=os.getenv("X402_NETWORK", "base"),
            pay_to_evm_address=os.getenv("PAY_TO_EVM_ADDRESS", ""),
            enable_cloud_collector=_bool(os.getenv("ENABLE_CLOUD_COLLECTOR"), False),
            station_ingest_token=os.getenv("STATION_INGEST_TOKEN", ""),
            ingest_max_age_seconds=_int("INGEST_MAX_AGE_SECONDS", 900),
            power_source_label=os.getenv("POWER_SOURCE_LABEL", "usb-wall-power"),
            estimated_power_watts=_float("ESTIMATED_POWER_WATTS", 1.5),
            power_status_file=os.getenv("POWER_STATUS_FILE", "~/.x402-temperature-power.json"),
            power_status_max_age_seconds=_int("POWER_STATUS_MAX_AGE_SECONDS", 180),
        )
