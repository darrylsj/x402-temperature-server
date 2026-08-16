import express from "express";

const ARCHITECTURES = new Set(["cloud", "edge"]);
const GATEWAY_MODES = new Set(["mock", "circle"]);

export function loadConfig(env = process.env) {
  const architecture = env.ARCHITECTURE || "edge";
  const gatewayMode = env.X402_GATEWAY_MODE || "mock";
  if (!ARCHITECTURES.has(architecture)) {
    throw new Error("ARCHITECTURE must be cloud or edge");
  }
  if (!GATEWAY_MODES.has(gatewayMode)) {
    throw new Error("X402_GATEWAY_MODE must be mock or circle");
  }
  return {
    architecture,
    gatewayMode,
    port: Number(env.PORT || "3090"),
    sensorOrigin: env.SENSOR_ORIGIN || "http://127.0.0.1:8080",
    sellerAddress: env.SELLER_ADDRESS || "0x0000000000000000000000000000000000000000",
    priceUsd: env.PRICE_USD || "0.001",
    facilitatorUrl: env.FACILITATOR_URL || "https://gateway-api-testnet.circle.com",
    publicBaseUrl: env.PUBLIC_BASE_URL || "",
  };
}

function paidPath(config) {
  return config.architecture === "cloud" ? "/temperature/latest" : "/temperature";
}

function paymentRequiredBody(config, path) {
  return {
    x402Version: 2,
    resource: {
      method: "GET",
      path,
      description:
        config.architecture === "cloud"
          ? "Latest posted simulated temperature reading from the cloud collector."
          : "Live simulated temperature reading from the self-contained edge sensor.",
      mimeType: "application/json",
    },
    accepts: [
      {
        scheme: "exact",
        network: "circle-gateway-testnet",
        asset: "USDC",
        amount: config.priceUsd,
        payTo: config.sellerAddress,
      },
    ],
  };
}

function mockPaymentGate(config, path) {
  return (req, res, next) => {
    const paidHeader = req.get("x-payment") || req.get("payment");
    if (paidHeader === "test-paid") {
      req.payment = {
        verified: true,
        payer: "local-test-buyer",
        amount: config.priceUsd,
        network: "mock",
      };
      next();
      return;
    }
    const body = paymentRequiredBody(config, path);
    res
      .status(402)
      .set("payment-required", Buffer.from(JSON.stringify(body)).toString("base64"))
      .json(body);
  };
}

async function paymentGate(config, path) {
  if (config.gatewayMode === "mock") {
    return mockPaymentGate(config, path);
  }
  if (!/^0x[a-fA-F0-9]{40}$/.test(config.sellerAddress)) {
    throw new Error("SELLER_ADDRESS must be a valid EVM address in circle mode");
  }
  const { createGatewayMiddleware } = await import("@circle-fin/x402-batching/server");
  const gateway = createGatewayMiddleware({
    sellerAddress: config.sellerAddress,
    facilitatorUrl: config.facilitatorUrl,
  });
  return gateway.require(`$${config.priceUsd}`);
}

async function forwardJson(req, res, config, upstreamPath) {
  const upstream = new URL(upstreamPath, config.sensorOrigin);
  const response = await fetch(upstream, { headers: { accept: "application/json" } });
  const text = await response.text();
  res.status(response.status);
  res.type(response.headers.get("content-type") || "application/json");
  if (req.payment) {
    res.set("x-payment-verified", "true");
  }
  res.send(text);
}

async function forwardIngest(req, res, config) {
  const upstream = new URL("/sensor-readings", config.sensorOrigin);
  const headers = {
    accept: "application/json",
    "content-type": "application/json",
  };
  const stationToken = req.get("x-station-token");
  if (stationToken) {
    headers["x-station-token"] = stationToken;
  }

  const response = await fetch(upstream, {
    method: "POST",
    headers,
    body: JSON.stringify(req.body || {}),
  });
  const text = await response.text();
  res.status(response.status);
  res.type(response.headers.get("content-type") || "application/json");
  res.send(text);
}

async function forwardManifest(req, res, config) {
  const upstream = new URL("/.well-known/x402-temperature.json", config.sensorOrigin);
  const response = await fetch(upstream, { headers: { accept: "application/json" } });
  const body = await response.json();
  const path = paidPath(config);
  const publicBaseUrl = config.publicBaseUrl || `${req.protocol}://${req.get("host")}`;

  res.status(response.status).json({
    ...body,
    public_base_url: publicBaseUrl,
    paid_endpoint: `GET ${path}`,
    paid_url: new URL(path, publicBaseUrl).toString(),
    price_usdc: config.priceUsd,
    seller_address: config.sellerAddress,
    payment: {
      gateway_mode: config.gatewayMode,
      scheme: config.gatewayMode === "circle" ? "GatewayWalletBatched" : "mock",
      facilitator_url: config.gatewayMode === "circle" ? config.facilitatorUrl : null,
    },
  });
}

export async function createProxyApp(config = loadConfig()) {
  const app = express();
  app.use(express.json({ limit: "32kb" }));
  const path = paidPath(config);
  const gate = await paymentGate(config, path);

  app.get("/health", async (req, res, next) => {
    try {
      await forwardJson(req, res, config, "/health");
    } catch (error) {
      next(error);
    }
  });

  app.get("/.well-known/x402-temperature.json", async (req, res, next) => {
    try {
      await forwardManifest(req, res, config);
    } catch (error) {
      next(error);
    }
  });

  app.get("/openapi.json", async (req, res, next) => {
    try {
      await forwardJson(req, res, config, "/openapi.json");
    } catch (error) {
      next(error);
    }
  });

  if (config.architecture === "cloud") {
    app.post("/sensor-readings", async (req, res, next) => {
      try {
        await forwardIngest(req, res, config);
      } catch (error) {
        next(error);
      }
    });
  }

  app.get(path, gate, async (req, res, next) => {
    try {
      await forwardJson(req, res, config, path);
    } catch (error) {
      next(error);
    }
  });

  app.use((req, res) => {
    res.status(404).json({
      error: "not_found",
      architecture: config.architecture,
      paid_endpoint: `GET ${path}`,
    });
  });

  return app;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();
  const app = await createProxyApp(config);
  app.listen(config.port, () => {
    console.log(
      `x402 temperature proxy listening on :${config.port} (${config.architecture}, ${config.gatewayMode})`,
    );
  });
}
