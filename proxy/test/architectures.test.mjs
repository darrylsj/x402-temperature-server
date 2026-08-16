import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import express from "express";
import request from "supertest";

import { createProxyApp } from "../src/server.mjs";

function startUpstream() {
  const app = express();
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
    res.json({ station: "roof-test-01", celsius: 21.4, stale: false, route: "edge" });
  });
  app.get("/temperature/latest", (req, res) => {
    res.json({ station: "roof-test-01", celsius: 20.8, stale: false, route: "cloud" });
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
    assert.equal(unpaid.body.resource.path, "/temperature");
    assert.equal(unpaid.body.accepts[0].amount, "0.001");
    assert.ok(unpaid.headers["payment-required"]);

    const paid = await request(app).get("/temperature").set("x-payment", "test-paid");
    assert.equal(paid.status, 200);
    assert.equal(paid.headers["x-payment-verified"], "true");
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
    assert.equal(unpaid.body.resource.path, "/temperature/latest");

    const paid = await request(app).get("/temperature/latest").set("x-payment", "test-paid");
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
});
