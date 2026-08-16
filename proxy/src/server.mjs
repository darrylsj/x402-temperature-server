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
    host: env.HOST || "",
    port: Number(env.PORT || "3090"),
    sensorOrigin: env.SENSOR_ORIGIN || "http://127.0.0.1:8080",
    sellerAddress: env.SELLER_ADDRESS || "0x0000000000000000000000000000000000000000",
    priceUsd: env.PRICE_USD || "0.001",
    facilitatorUrl: env.FACILITATOR_URL || "https://gateway-api-testnet.circle.com",
    publicBaseUrl: env.PUBLIC_BASE_URL || "",
    forwardMockPayment: env.FORWARD_MOCK_PAYMENT === "true",
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function demoPage(config, publicBaseUrl, path) {
  const paidUrl = new URL(path, publicBaseUrl).toString();
  const chain = config.gatewayMode === "circle" ? "MATIC-AMOY" : "mock";
  const payCommand =
    config.gatewayMode === "circle"
      ? `circle services pay ${paidUrl} -X GET --address "$BUYER_ADDRESS" --chain ${chain} --max-amount ${config.priceUsd} --output json`
      : `curl -H 'x-payment: test-paid' ${paidUrl}`;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>x402 Temperature Public Demo</title>
  <style>
    :root { color-scheme: light dark; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f6f7f9; color: #17202a; }
    main { max-width: 920px; margin: 0 auto; padding: 32px 20px 48px; }
    h1 { font-size: 28px; margin: 0 0 8px; letter-spacing: 0; }
    h2 { font-size: 18px; margin: 28px 0 10px; letter-spacing: 0; }
    p { line-height: 1.5; }
    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #111827; color: #e5e7eb; padding: 14px; border-radius: 8px; }
    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 22px 0; }
    .tile { border: 1px solid #d8dee8; border-radius: 8px; padding: 12px; background: #fff; }
    .label { color: #536170; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    .value { margin-top: 4px; font-weight: 650; overflow-wrap: anywhere; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; }
    button, a.button { border: 1px solid #ccd3dd; background: #fff; color: #17202a; border-radius: 8px; padding: 10px 12px; text-decoration: none; cursor: pointer; font-weight: 650; }
    button:hover, a.button:hover { background: #eef2f7; }
    #output { min-height: 150px; }
    @media (prefers-color-scheme: dark) {
      body { background: #0f1720; color: #edf2f7; }
      .tile, button, a.button { background: #151f2b; color: #edf2f7; border-color: #2b3746; }
      button:hover, a.button:hover { background: #1d2937; }
      .label { color: #9aa7b7; }
    }
  </style>
</head>
<body>
  <main>
    <h1>x402 Temperature Public Demo</h1>
    <p>This page is public and free. The temperature payload is protected by x402 and returns <code>402 Payment Required</code> until a buyer agent sends valid Circle Gateway payment proof.</p>
    <div class="meta">
      <div class="tile"><div class="label">Architecture</div><div class="value">${escapeHtml(config.architecture)}</div></div>
      <div class="tile"><div class="label">Gateway Mode</div><div class="value">${escapeHtml(config.gatewayMode)}</div></div>
      <div class="tile"><div class="label">Price</div><div class="value">${escapeHtml(config.priceUsd)} USDC</div></div>
      <div class="tile"><div class="label">Paid Route</div><div class="value">GET ${escapeHtml(path)}</div></div>
    </div>
    <div class="actions">
      <button type="button" data-url="/health">Health</button>
      <button type="button" data-url="/.well-known/x402-temperature.json">Manifest</button>
      <button type="button" data-url="${escapeHtml(path)}">Unpaid 402</button>
      <a class="button" href="${escapeHtml(paidUrl)}">Open Paid URL</a>
    </div>
    <h2>Paid Buyer Command</h2>
    <pre>${escapeHtml(payCommand)}</pre>
    <h2>Output</h2>
    <pre id="output">Click Health, Manifest, or Unpaid 402.</pre>
  </main>
  <script>
    async function callPath(path) {
      const output = document.getElementById('output');
      output.textContent = 'Loading ' + path + ' ...';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const res = await fetch(path, {
          headers: { accept: 'application/json', 'ngrok-skip-browser-warning': 'true' },
          cache: 'no-store',
          signal: controller.signal
        });
        const text = await res.text();
        output.textContent = res.status + ' ' + res.statusText + '\\n\\n' + text;
      } catch (error) {
        output.textContent = error.name === 'AbortError' ? 'Timed out after 8000 ms.' : String(error);
      } finally {
        clearTimeout(timeout);
      }
    }
    for (const button of document.querySelectorAll('button[data-url]')) {
      button.addEventListener('click', () => callPath(button.dataset.url));
    }
  </script>
</body>
</html>`;
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
  const headers = { accept: "application/json" };
  if (config.forwardMockPayment && req.payment) {
    headers["x-payment"] = "test-paid";
  }
  const response = await fetch(upstream, { headers });
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

  app.get(["/", "/demo"], (req, res) => {
    const publicBaseUrl = config.publicBaseUrl || `${req.protocol}://${req.get("host")}`;
    res
      .status(200)
      .set("Cache-Control", "no-store")
      .type("html")
      .send(demoPage(config, publicBaseUrl, path));
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
  app.listen(config.port, config.host || undefined, () => {
    console.log(
      `x402 temperature proxy listening on ${config.host || "0.0.0.0"}:${config.port} (${config.architecture}, ${config.gatewayMode})`,
    );
  });
}
