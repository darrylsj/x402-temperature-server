# Paid Buyer Test

This runbook captures the first successful external x402 buyer test for the Danville temperature service.

## Live Seller Endpoint

```text
https://x402-temperature.ngrok.app/temperature/latest
```

Current seller shape:

```text
buyer agent
  -> stable ngrok HTTPS endpoint
  -> SIM cloud server ngrok agent
  -> Node/Express Circle Gateway proxy on 127.0.0.1:3090
  -> Python cloud collector on 127.0.0.1:8091
  -> latest Danville reading published by the x402host Pi
```

## Price and Network

```text
price: 0.001 USDC
scheme: GatewayWalletBatched
testnet buyer network used: Polygon Amoy
paid route: GET /temperature/latest
```

The service should inspect as payable:

```bash
circle services inspect \
  https://x402-temperature.ngrok.app/temperature/latest \
  --output json
```

## Buyer Wallet Preparation

Create or use a Circle testnet agent wallet, fund it from the faucet, then deposit testnet USDC into Gateway.

```bash
circle wallet create --testnet --output json

circle wallet fund \
  --address "$BUYER_ADDRESS" \
  --chain MATIC-AMOY \
  --token usdc \
  --testnet \
  --output json

circle gateway deposit \
  --amount 0.5 \
  --address "$BUYER_ADDRESS" \
  --chain MATIC-AMOY \
  --method direct \
  --output json

circle gateway balance \
  --address "$BUYER_ADDRESS" \
  --chain MATIC-AMOY \
  --all \
  --output json
```

Gateway balance must be non-zero before paid requests can succeed.

## Estimate

Always estimate before the first paid request:

```bash
circle services pay \
  https://x402-temperature.ngrok.app/temperature/latest \
  -X GET \
  --address "$BUYER_ADDRESS" \
  --chain MATIC-AMOY \
  --max-amount 0.001 \
  --estimate \
  --output json
```

Expected result:

```text
Payment required: $0.001 USDC
chain: Polygon Amoy
scheme: GatewayWalletBatched
```

## Paid Call

```bash
circle services pay \
  https://x402-temperature.ngrok.app/temperature/latest \
  -X GET \
  --address "$BUYER_ADDRESS" \
  --chain MATIC-AMOY \
  --max-amount 0.001 \
  --output json
```

Expected response:

```json
{
  "data": {
    "response": {
      "station": "danville-demo-01",
      "location": "Danville, CA",
      "fahrenheit": 71.92,
      "stale": false
    },
    "payment": {
      "amount": "$0.001 USDC",
      "chain": "Polygon Amoy",
      "scheme": "GatewayWalletBatched"
    }
  }
}
```

## Confirmed Batch Result

On 2026-08-15 Pacific time, the public seller endpoint completed a 50-purchase test run:

```text
successful paid purchases: 50
failed paid purchases: 0
price per purchase: 0.001 testnet USDC
total spent from Gateway balance: 0.05 testnet USDC
remaining Gateway balance after run: 0.45 testnet USDC
```

The final paid response returned fresh Danville data:

```json
{
  "station": "danville-demo-01",
  "location": "Danville, CA",
  "fahrenheit": 71.92,
  "celsius": 22.18,
  "stale": false
}
```

## Base Sepolia Caveat

The first buyer attempt used Base Sepolia. The wallet funded correctly, but Gateway balance did not credit after direct and eco deposits even though wallet USDC was debited. A paid request on that path failed with:

```text
Payment submitted but request failed with HTTP 402
Server response: Insufficient Gateway balance
```

For the current testnet buyer workflow, prefer Polygon Amoy until the Base Sepolia Gateway-credit issue is resolved. A Circle CLI bug report was submitted for the Base Sepolia issue.

## Safety

The confirmed 50-call run used testnet USDC. Do not switch this runbook to mainnet without explicit approval for the exact amount, seller address, buyer wallet, and network.
