#!/usr/bin/env bash
# Build and upload the public site to Cloudflare Workers:
#   https://pathway-to-sunshine.joelcomm.workers.dev
# Needs Cloudflare API access (CLOUDFLARE_API_TOKEN, or a proxy that adds it).
set -euo pipefail
cd "$(dirname "$0")"
ACCOUNT="${CLOUDFLARE_ACCOUNT_ID:-c4e25d6b38aa096cb6e9f4d17faebf24}"
NAME="pathway-to-sunshine"
API="https://api.cloudflare.com/client/v4/accounts/$ACCOUNT/workers/scripts/$NAME"
AUTH=()
if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then AUTH=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"); fi

python3 build_site.py

curl -sS --fail-with-body -X PUT "$API" "${AUTH[@]}" \
  -F 'metadata={"main_module":"worker.js","compatibility_date":"2025-06-01"};type=application/json' \
  -F 'worker.js=@site/worker.js;type=application/javascript+module' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("upload ok" if d.get("success") else d)'

curl -sS --fail-with-body -X POST "$API/subdomain" "${AUTH[@]}" -H 'content-type: application/json' \
  --data '{"enabled":true,"previews_enabled":false}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("workers.dev route ok" if d.get("success") else d)'

echo "Live at https://$NAME.joelcomm.workers.dev"
