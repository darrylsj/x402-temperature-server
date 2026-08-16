#!/usr/bin/env node
import { CdpX402Client } from "@coinbase/cdp-sdk/x402";
import { wrapFetchWithPayment } from "@x402/fetch";

const url = process.argv[2];
if (!url || !/^https:\/\/[^\s"'`<>]+$/.test(url)) {
  console.error("Usage: node scripts/pay-coinbase-client.mjs https://host.example/temperature");
  process.exit(2);
}

const environment = process.env.CDP_X402_ENVIRONMENT || "development";
const client = new CdpX402Client({ environment });
const { evmAddress, svmAddress } = await client.getAddresses();
const fetchWithPayment = wrapFetchWithPayment(globalThis.fetch, client);

const response = await fetchWithPayment(url, {
  headers: {
    accept: "application/json",
    "ngrok-skip-browser-warning": "true",
  },
});
const text = await response.text();
let body = text;
try {
  body = JSON.parse(text);
} catch {
  // Leave non-JSON responses as text for debugging.
}

console.log(
  JSON.stringify(
    {
      facilitator: "Coinbase CDP",
      environment,
      payer: { evmAddress, svmAddress },
      status: response.status,
      ok: response.ok,
      body,
    },
    null,
    2,
  ),
);
