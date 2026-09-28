import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import express from "express";
import request from "supertest";

import { createProxyApp, loadConfig } from "../src/server.mjs";

let requireForwardedPayment = false;

function startUpstream() {
  const app = express();
  app.use(express.json());
  app.get("/health", (req, res) => {
    res.json({ ok: true, station: "roof-test-01" });
  });
  app.get("/.well-known/x402-temperature.json", (req, res) => {
    res.json({ name: "x402 Temperature Server", station: "roof-test-01" });
  });
  app.get("/openapi.json", (req, res) => {
    res.json({ openapi: "3.1.0", info: { title: "x402 Temperature Server" } });
  });
  app.get("/temperature", (req, res) => {
    if (requireForwardedPayment && req.get("x-mock-payment") !== "test-paid") {
      res.status(402).json({ upstream: "missing forwarded payment" });
      return;
    }
    res.json({ station: "roof-test-01", celsius: 21.4, stale: false, route: "edge" });
  });
  app.get("/temperature/latest", (req, res) => {
    res.json({ station: "roof-test-01", celsius: 20.8, stale: false, route: "cloud" });
  });
  app.post("/sensor-readings", (req, res) => {
    if (req.get("x-station-token") !== "station-secret") {
      res.status(401).json({ detail: "invalid station token" });
      return;
    }
    res.json({ accepted: true, station: req.body.station, route: "ingest" });
  });
  return new Promise((resolve) => {
    const server = app.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({ server, origin: `http://127.0.0.1:${address.port}` });
    });
  });
}

describe("mock x402 proxy architectures", () => {
  let upstream;

  before(async () => {
    upstream = await startUpstream();
  });

  after(() => {
    upstream.server.close();
  });

  it("gates the self-contained edge temperature route and forwards after test payment", async () => {
    const app = await createProxyApp({
      architecture: "edge",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
    });

    const unpaid = await request(app).get("/temperature");
    assert.equal(unpaid.status, 402);
    assert.ok(unpaid.body.resource.url.endsWith("/temperature"));
    assert.equal(unpaid.body.x402Version, 2);
    assert.equal(unpaid.body.accepts[0].network, "eip155:84532");
    assert.equal(unpaid.body.accepts[0].amount, "1000");
    assert.equal(
      unpaid.body.accepts[0].asset,
      "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    );
    assert.equal(unpaid.body.accepts[0].maxTimeoutSeconds, 300);
    assert.deepEqual(unpaid.body.accepts[0].extra, { name: "USDC", version: "2" });
    assert.ok(unpaid.headers["payment-required"]);

    const legacy = await request(app).get("/temperature").set("x-payment", "test-paid");
    assert.equal(legacy.status, 402);

    const paid = await request(app).get("/temperature").set("x-mock-payment", "test-paid");
    assert.equal(paid.status, 200);
    assert.equal(paid.headers["x-mock-payment-verified"], "true");
    assert.equal(paid.body.route, "edge");
  });

  it("can forward local mock payment proof to a simulated upstream after proxy payment", async () => {
    requireForwardedPayment = true;
    const app = await createProxyApp({
      architecture: "edge",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
      forwardMockPayment: true,
    });

    let paid;
    try {
      paid = await request(app)
        .get("/temperature")
        .set("x-mock-payment", "test-paid");
    } finally {
      requireForwardedPayment = false;
    }
    assert.equal(paid.status, 200);
    assert.equal(paid.body.route, "edge");
  });

  it("gates the cloud collector latest-reading route and forwards after test payment", async () => {
    const app = await createProxyApp({
      architecture: "cloud",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
    });

    const unpaid = await request(app).get("/temperature/latest");
    assert.equal(unpaid.status, 402);
    assert.ok(unpaid.body.resource.url.endsWith("/temperature/latest"));

    const paid = await request(app).get("/temperature/latest").set("x-mock-payment", "test-paid");
    assert.equal(paid.status, 200);
    assert.equal(paid.body.route, "cloud");
  });

  it("leaves health and discovery endpoints free", async () => {
    const app = await createProxyApp({
      architecture: "cloud",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
      publicBaseUrl: "https://x402-temperature.example",
    });

    assert.equal((await request(app).get("/health")).status, 200);
    const manifest = await request(app).get("/.well-known/x402-temperature.json");
    assert.equal(manifest.status, 200);
    assert.equal(manifest.body.public_base_url, "https://x402-temperature.example");
    assert.equal(manifest.body.paid_endpoint, "GET /temperature/latest");
    assert.equal(
      manifest.body.paid_url,
      "https://x402-temperature.example/temperature/latest",
    );
    assert.equal(manifest.body.payment.scheme, "mock");
    assert.equal((await request(app).get("/openapi.json")).status, 200);
  });

  it("serves a public browser demo page from the proxy", async () => {
    const app = await createProxyApp({
      architecture: "cloud",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
      publicBaseUrl: "https://x402-temperature.example",
    });

    const demo = await request(app).get("/demo");
    assert.equal(demo.status, 200);
    assert.match(demo.text, /Danville x402 Temperature Public Demo/);
    assert.match(demo.text, /Sycamore Valley Park/);
    assert.match(demo.text, /https:\/\/x402-temperature\.example\/temperature\/latest/);
    assert.match(demo.text, /GET \/temperature\/latest/);
  });

  it("passes authenticated cloud station ingest through without buyer payment", async () => {
    const app = await createProxyApp({
      architecture: "cloud",
      gatewayMode: "mock",
      sensorOrigin: upstream.origin,
      sellerAddress: "0x0000000000000000000000000000000000000000",
      priceUsd: "0.001",
    });

    const accepted = await request(app)
      .post("/sensor-readings")
      .set("x-station-token", "station-secret")
      .send({ station: "danville-demo-01", celsius: 22.1 });
    assert.equal(accepted.status, 200);
    assert.equal(accepted.body.route, "ingest");
    assert.equal(accepted.body.station, "danville-demo-01");

    const rejected = await request(app)
      .post("/sensor-readings")
      .set("x-station-token", "wrong")
      .send({ station: "danville-demo-01", celsius: 22.1 });
    assert.equal(rejected.status, 401);
  });

  it("accepts coinbase as the edge facilitator mode", () => {
    const config = loadConfig({
      ARCHITECTURE: "edge",
      X402_GATEWAY_MODE: "coinbase",
      SENSOR_ORIGIN: upstream.origin,
      PRICE_USD: "0.001",
      PUBLIC_BASE_URL: "https://x402-temperature-edge.example",
    });

    assert.equal(config.architecture, "edge");
    assert.equal(config.gatewayMode, "coinbase");
    assert.equal(config.coinbaseEnvironment, "development");
  });
});
