#!/usr/bin/env python3
"""Monitor an INA219 UPS/battery sensor for the x402 temperature station.

Writes two files:
- CSV history for spreadsheet/debugging.
- JSON status consumed by the FastAPI /health endpoint.

The script is safe to install before the hardware is present, but it will not
produce measured power until an INA219-compatible HAT/sensor is connected and
I2C is enabled.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

from ina219 import DeviceRangeError, INA219


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def battery_percent_from_voltage(voltage: float, empty: float, full: float) -> float:
    if full <= empty:
        return 0.0
    return max(0.0, min(100.0, ((voltage - empty) / (full - empty)) * 100.0))


def setup_sensor(shunt_ohms: float) -> INA219:
    ina = INA219(shunt_ohms)
    ina.configure()
    return ina


def read_battery(ina: INA219) -> tuple[float, float | None, float | None]:
    voltage = ina.voltage()
    try:
        current = ina.current()
        power = ina.power()
    except DeviceRangeError:
        current = None
        power = None
    return voltage, current, power


def append_csv(path: Path, voltage: float, current: float | None, power: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_is_new = not path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if file_is_new:
            writer.writerow(["timestamp", "voltage_v", "current_ma", "power_mw"])
        writer.writerow(
            [
                iso_now(),
                round(voltage, 3),
                "" if current is None else round(current, 1),
                "" if power is None else round(power, 1),
            ]
        )


def write_status(
    path: Path,
    voltage: float,
    current: float | None,
    power: float | None,
    battery_percent: float,
    shutdown_voltage: float,
    low_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": iso_now(),
        "source": "ina219",
        "voltage_v": round(voltage, 3),
        "current_ma": None if current is None else round(current, 1),
        "power_mw": None if power is None else round(power, 1),
        "battery_percent": round(battery_percent, 1),
        "shutdown_voltage": shutdown_voltage,
        "low_readings": low_count,
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True) + "\n")
    tmp_path.replace(path)


def safe_shutdown() -> None:
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shutdown-voltage", type=float, default=3.30)
    parser.add_argument("--low-readings-required", type=int, default=3)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--shunt-ohms", type=float, default=0.1)
    parser.add_argument("--empty-voltage", type=float, default=3.2)
    parser.add_argument("--full-voltage", type=float, default=4.2)
    parser.add_argument("--log-file", default="~/battery_log.csv")
    parser.add_argument("--status-file", default="~/.x402-temperature-power.json")
    parser.add_argument("--no-shutdown", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_path = Path(os.path.expanduser(args.log_file))
    status_path = Path(os.path.expanduser(args.status_file))
    ina = setup_sensor(args.shunt_ohms)
    low_count = 0

    print("Starting INA219 battery monitor")
    print(f"CSV log: {log_path}")
    print(f"Status JSON: {status_path}")
    print(f"Shutdown threshold: {args.shutdown_voltage} V")

    while True:
        voltage, current, power = read_battery(ina)
        battery_percent = battery_percent_from_voltage(voltage, args.empty_voltage, args.full_voltage)
        append_csv(log_path, voltage, current, power)

        if voltage < args.shutdown_voltage:
            low_count += 1
        else:
            low_count = 0

        write_status(status_path, voltage, current, power, battery_percent, args.shutdown_voltage, low_count)

        current_text = "n/a" if current is None else f"{current:.0f} mA"
        power_text = "n/a" if power is None else f"{power / 1000:.2f} W"
        print(
            f"{datetime.now().strftime('%H:%M:%S')} "
            f"battery={voltage:.2f} V current={current_text} power={power_text} "
            f"soc={battery_percent:.0f}% low={low_count}/{args.low_readings_required}",
            flush=True,
        )

        if low_count >= args.low_readings_required:
            print("Battery critically low", flush=True)
            if not args.no_shutdown:
                safe_shutdown()
            break

        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
