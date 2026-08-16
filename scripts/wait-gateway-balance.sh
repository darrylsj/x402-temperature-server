#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/wait-gateway-balance.sh --address 0x... --chain CHAIN --minimum 0.05 [--timeout-seconds 1200]

Example:
  scripts/wait-gateway-balance.sh \
    --address "$BUYER_ADDRESS" \
    --chain BASE-SEPOLIA \
    --minimum 0.05 \
    --timeout-seconds 1500
EOF
}

ADDRESS=""
CHAIN=""
MINIMUM=""
TIMEOUT_SECONDS=1200
INTERVAL_SECONDS=15

while [[ $# -gt 0 ]]; do
  case "$1" in
    --address)
      ADDRESS="${2:-}"
      shift 2
      ;;
    --chain)
      CHAIN="${2:-}"
      shift 2
      ;;
    --minimum)
      MINIMUM="${2:-}"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$ADDRESS" =~ ^0x[a-fA-F0-9]{40}$ ]]; then
  echo "--address must be an EVM address" >&2
  exit 2
fi
if [[ -z "$CHAIN" || -z "$MINIMUM" ]]; then
  usage
  exit 2
fi
if ! command -v circle >/dev/null 2>&1; then
  echo "circle CLI is required" >&2
  exit 127
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 127
fi

deadline=$((SECONDS + TIMEOUT_SECONDS))

while (( SECONDS <= deadline )); do
  output="$(circle gateway balance --address "$ADDRESS" --chain "$CHAIN" --all --output json)"
  total="$(jq -r '.data.total // "0"' <<<"$output")"
  printf 'gateway_total=%s required=%s chain=%s\n' "$total" "$MINIMUM" "$CHAIN"

  if awk "BEGIN { exit !($total >= $MINIMUM) }"; then
    jq '.data' <<<"$output"
    exit 0
  fi

  sleep "$INTERVAL_SECONDS"
done

echo "Timed out waiting for Gateway balance >= ${MINIMUM} on ${CHAIN}" >&2
exit 1
