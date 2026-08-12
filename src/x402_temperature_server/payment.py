from __future__ import annotations

from fastapi import FastAPI

from .config import Settings


def install_x402(app: FastAPI, settings: Settings) -> None:
    if not settings.pay_to_evm_address:
        raise RuntimeError("PAY_TO_EVM_ADDRESS is required when ENABLE_X402=true")

    try:
        from cdp.x402 import create_facilitator_config
        from x402.facilitator import HTTPFacilitatorClient
        from x402.fastapi.middleware import PaymentMiddlewareASGI
        from x402.types import PaymentOption, Resource, RouteConfig
        from x402.extensions import discoverable
        from x402.servers import x402ResourceServer
        from x402.schemes.exact.evm import ExactEvmServerScheme
    except ImportError as exc:
        raise RuntimeError(
            "Install x402 dependencies first: python -m pip install '.[x402]'"
        ) from exc

    facilitator = HTTPFacilitatorClient(create_facilitator_config())
    server = x402ResourceServer(facilitator)
    server.register(settings.x402_network, ExactEvmServerScheme())

    route = RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                network=settings.x402_network,
                pay_to=settings.pay_to_evm_address,
                amount=settings.x402_price_usd,
                asset="USDC",
            )
        ],
        resource=Resource(
            method="GET",
            path="/temperature",
            description=f"Live temperature reading from {settings.location_label}",
        ),
        extensions=[
            discoverable(
                name=f"{settings.station_id} live temperature",
                description="Paid hyperlocal temperature, humidity, and pressure reading from a Raspberry Pi sensor.",
                output_schema={
                    "type": "object",
                    "required": ["station", "celsius", "fahrenheit", "read_at"],
                    "properties": {
                        "station": {"type": "string"},
                        "celsius": {"type": "number"},
                        "fahrenheit": {"type": "number"},
                        "humidity": {"type": ["number", "null"]},
                        "pressure_hpa": {"type": ["number", "null"]},
                        "read_at": {"type": "string", "format": "date-time"},
                    },
                },
            )
        ],
    )

    app.add_middleware(PaymentMiddlewareASGI, routes={"GET /temperature": route}, server=server)

