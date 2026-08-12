# Hardware Diagrams

These diagrams are intentionally simple enough to build from at a bench.

## BME280 I2C Wiring

Use this for the first prototype.

```text
Top view: Raspberry Pi Zero 2 W 40-pin header

  Pin 1  3V3   o o  5V   Pin 2
  Pin 3  SDA   o o  5V   Pin 4
  Pin 5  SCL   o o  GND  Pin 6
  Pin 7  GPIO4 o o  TXD  Pin 8
  Pin 9  GND   o o  RXD  Pin 10

BME280 breakout

  VIN  <---------------- Pin 1  3V3
  GND  <---------------- Pin 6  GND
  SCK  <---------------- Pin 5  GPIO3 / SCL
  SDI  <---------------- Pin 3  GPIO2 / SDA
```

Pin table:

| BME280 pin | Raspberry Pi pin | Function |
| --- | --- | --- |
| VIN | Pin 1 | 3.3 V power |
| GND | Pin 6 | Ground |
| SCK / SCL | Pin 5 | I2C clock |
| SDI / SDA | Pin 3 | I2C data |

Notes:

- Use 3.3 V.
- Most BME280 boards appear at I2C address `0x76` or `0x77`.
- Run `i2cdetect -y 1` after enabling I2C.

## DS18B20 Wiring

Use this for a waterproof outdoor temperature probe.

```text
Raspberry Pi Zero 2 W                 DS18B20 probe

Pin 1  3V3   -----------------------> Red / VDD
Pin 6  GND   -----------------------> Black / GND
Pin 7  GPIO4 -----------------------> Yellow / DATA

4.7k resistor:

Pin 1  3V3   ----[ 4.7k ]---- Pin 7 GPIO4 / DATA
```

Enable 1-Wire:

```bash
sudo raspi-config nonint do_onewire 0
sudo reboot
```

Then check for a sensor path:

```bash
ls /sys/bus/w1/devices/28-*/w1_slave
```

## Wired Indoor Layout

```text
Wall outlet
  -> Pi USB power supply
  -> Raspberry Pi Zero 2 W
  -> I2C jumper wires
  -> BME280 sensor
  -> local Wi-Fi
```

## Solar Outdoor Layout

```text
Sun
  -> 10 W solar panel
  -> Voltaic V75 battery solar input
  -> V75 Always On USB-A output
  -> Raspberry Pi Zero 2 W power input
  -> BME280 or DS18B20 sensor
  -> Wi-Fi
```

Placement notes:

- Put the solar panel in direct sun.
- Keep the battery shaded and inside the enclosure.
- Keep the temperature sensor out of direct sun or use a radiation shield.
- Do not seal electronics in an unventilated box that will sit in summer sun.

## Cloud Collector Network Diagram

```text
Pi sensor node
  reads sensor every 60 seconds
  POSTs reading with station token
        |
        v
Cheap cloud VPS
  validates reading
  stores latest reading
  exposes x402 paid endpoint
        |
        v
Buyer agents pay and retrieve latest reading
```

## Self-Contained Pi Network Diagram

```text
Buyer agents
  -> public HTTPS route
  -> Cloudflare Tunnel / Caddy / Tailscale Funnel
  -> Raspberry Pi x402 payment proxy
  -> localhost FastAPI sensor service
  -> live sensor read
```
