# Solar And Battery Power Option

This is the optional off-grid power design for the x402 temperature station. Build and verify the wired indoor version first, then move to solar.

## Power Budget

A Raspberry Pi Zero 2 W plus a BME280 sensor is a small but still meaningful continuous load. Size the power system for the Pi, Wi-Fi, the sensor, conversion losses, and cloudy periods.

Conservative planning load:

- Pi Zero 2 W with Wi-Fi: 1.0-1.5 W typical for this service profile
- BME280 sensor: negligible compared with the Pi
- USB conversion and battery overhead: plan for 15-25%

Planning number:

```text
1.5 W x 24 hours = 36 Wh/day
Add 20% overhead = about 43 Wh/day
```

This means a 48 Wh battery is roughly one day of backup at the conservative load. A 72 Wh battery is a better field choice because it gives more overnight and cloudy-day margin.

## Recommended V1 Solar Kit

Use this for a practical first outdoor prototype:

- Voltaic V75 USB Battery Pack, 20,100 mAh / 72 Wh, Always On output, pass-through solar charging
- Voltaic 10 Watt 6 Volt ETFE Solar Panel
- Voltaic 3.5 x 1.1 mm solar cable or extension, if the panel cannot sit next to the enclosure
- USB-A to micro USB cable from the battery to the Raspberry Pi Zero 2 W power port
- Weatherproof enclosure for the Pi and battery
- Mounting bracket or hardware for the solar panel

Why V75 instead of V50:

- V50 is 48 Wh and can work for a short test.
- V75 is 72 Wh and is the better always-on field design.
- Both support Always On mode on USB-A outputs, which matters because many ordinary power banks shut off under low or steady IoT loads.

Use the battery USB-A Always On output for the Pi. Do not power the Pi from the USB-C PD port in this design because Voltaic documents USB-C PD as not Always On compatible.

## Lower-Cost Test Option

For bench testing only:

- Voltaic V50 USB Battery Pack, 13,400 mAh / 48 Wh
- Voltaic 10 Watt 6 Volt ETFE Solar Panel

This is useful for validating solar charging and runtime behavior, but it is tight for full-time operation if the Pi spends much time near 1.5 W.

## Expected Runtime

Approximate battery-only runtime:

```text
V50: 48 Wh / 1.5 W = 32 hours before conversion losses
V75: 72 Wh / 1.5 W = 48 hours before conversion losses
```

With conversion losses and temperature effects, expect less. The V75 is the sensible default for an unattended station.

## Deployment Notes

- Mount the solar panel where it gets direct sun for the middle of the day.
- Keep the battery out of direct sun and inside the weatherproof enclosure.
- Add ventilation or shade for the electronics; sealed boxes get hot.
- Start with 10 W solar, then move to 20 W if the battery trends downward over several days.
- Log battery voltage or daily uptime before declaring the station production-ready.

## Suggested Future Enhancements

- Add a `/power` endpoint that reports battery voltage or state-of-charge when the hardware exposes it.
- Add a low-power mode that lowers read frequency or disables nonessential services if battery is low.
- Add a watchdog restart and daily uptime counter.
- Publish solar/battery status in the paid payload only if the station owner wants buyers to see the station health.
