# Hardware Ordering Guide

This page lists the parts needed to build the x402 temperature station.

## Minimum Wired Prototype

| Qty | Item | Example URL | Expected price | Notes |
| --- | --- | --- | --- | --- |
| 1 | Raspberry Pi Zero 2 W Starter Kit | https://www.pishop.us/product/raspberry-pi-zero-2-w-starter-kit/ | USD 74.95 | Includes Pi Zero 2 W, microSD, power supply, and basic accessories in the PiShop bundle. |
| 1 | Adafruit BME280 I2C or SPI Temperature Humidity Pressure Sensor | https://www.pishop.us/product/adafruit-bme280-i2c-or-spi-temperature-humidity-pressure-sensor/ | USD 14.95 | The first sensor path for the book demo. |
| 1 | Female-to-female jumper wire set | PiShop, Adafruit, Amazon, or included kit accessories | varies | Needed if the starter kit does not include enough GPIO jumpers. |

PiShop checkout observed on 2026-08-12:

```text
Raspberry Pi Zero 2 W Starter Kit: USD 74.95
Adafruit BME280 sensor:          USD 14.95
Subtotal:                        USD 89.90
USPS Priority Mail:              USD 11.51
Tax to Danville, CA:             USD 7.87
Total:                           USD 109.28
```

## Outdoor Sensor Option

Use this when the Pi is inside an enclosure but the temperature probe needs to sit outside.

| Qty | Item | Notes |
| --- | --- | --- |
| 1 | DS18B20 waterproof temperature probe | Temperature-only, but robust outdoors. |
| 1 | 4.7k resistor | Pull-up resistor between 3.3 V and data line. |
| 1 | Weatherproof enclosure | Keep the Pi and battery dry. |
| 1 | Radiation shield | Prevent direct sun from warming the sensor body. |

The BME280 is better for a first indoor or sheltered demo because it includes humidity and pressure. The DS18B20 is better when the sensor must be outside in weather.

## Solar And Battery Option

Recommended first field prototype:

| Qty | Item | Example URL | Expected price | Notes |
| --- | --- | --- | --- | --- |
| 1 | Voltaic V75 USB Battery Pack | https://voltaicsystems.com/v75 | about USD 89 | 20,100 mAh / 72 Wh, Always On USB output. |
| 1 | Voltaic 10 Watt 6 Volt ETFE Solar Panel | https://voltaicsystems.com/10-watt-panel-etfe/ | about USD 65 | Weather-resistant panel for solar charging. |
| 1 | USB-A to micro USB cable | any reliable cable | varies | Battery to Raspberry Pi Zero 2 W power input. |
| 1 | 3.5 x 1.1 mm solar extension cable | Voltaic or equivalent | varies | Optional, only if the panel is away from the enclosure. |
| 1 | Outdoor enclosure and mounting hardware | any suitable supplier | varies | Protects battery and Pi; mounts panel. |

See [solar-power.md](solar-power.md) for watt-hour sizing.

## Cloud Server Option

For the cloud collector design:

| Provider | Approximate cost | Recommendation |
| --- | --- | --- |
| RackNerd 1 GB KVM VPS special | about USD 21.99/year when available | Best practical cheap host for the reference design. |
| VPS1Dollar | from about USD 1/month | Strict cost demo, but IPv6-first/NAT64 caveats. |
| IONOS VPS XS | often about USD 2/month or higher | More mainstream fallback. |

The cloud server is optional for the wired prototype but recommended for the public x402 seller design.

## Buy Sequence

1. Buy the wired Pi + BME280 parts first.
2. Build and verify local readings.
3. Add the cloud VPS if using the cloud collector design.
4. Add the Voltaic battery and panel after the wired station is stable.
5. Add outdoor enclosure, DS18B20, and radiation shield only when moving outside.
