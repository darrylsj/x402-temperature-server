# Raspberry Pi Build Notes

This is the hardware path for the book demo.

## Wiring BME280 Over I2C

Use 3.3V, not 5V.

| BME280 pin | Raspberry Pi pin |
| --- | --- |
| VIN | 1, 3V3 |
| GND | 6, GND |
| SCK / SCL | 5, GPIO3 / SCL |
| SDI / SDA | 3, GPIO2 / SDA |

Enable I2C:

```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

Confirm the sensor is visible:

```bash
i2cdetect -y 1
```

Most BME280 boards appear at `0x76` or `0x77`.

## Wiring DS18B20

The waterproof DS18B20 is a good alternative when you only need temperature.

- Red: 3.3V
- Black: ground
- Yellow/data: GPIO4, physical pin 7
- 4.7k resistor between red and yellow/data

Enable 1-Wire:

```bash
sudo raspi-config nonint do_onewire 0
sudo reboot
```

## Install On The Pi

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip i2c-tools
git clone https://github.com/darrylsj/x402-temperature-server.git
cd x402-temperature-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[sensor,x402]'
cp .env.example .env
```

Edit `.env`, then run:

```bash
python -m x402_temperature_server
```

## Production Service

```bash
sudo mkdir -p /opt
sudo cp -R "$PWD" /opt/x402-temperature-server
sudo cp systemd/x402-temperature-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x402-temperature-server
sudo systemctl status x402-temperature-server
```

Expose the service over HTTPS with Cloudflare Tunnel, Caddy, or another reverse proxy. Bazaar validation requires a public HTTPS URL.

