"""
Simulates the shop backend sending a refund webhook to the TAGGRS server container.

Usage:
    export TAGGRS_URL="https://your-tagging-server-url"
    export WEBHOOK_SECRET="the-secret-configured-in-the-GTM-client"
    python webhook/send_refund.py T-1791905010483 24.90

To see the request in GTM server Preview, also set:
    export GTM_PREVIEW_HEADER="<value from Preview → ⋮ → Send requests manually>"

Optional tests of the client's error handling:
    python webhook/send_refund.py T-123 24.90 --wrong-secret   -> expect 401
    python webhook/send_refund.py T-123 0                       -> expect 400
"""
import argparse
import os
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a refund webhook to the server container.")
    parser.add_argument("transaction_id", help="transaction_id of the original purchase, e.g. T-1791905010483")
    parser.add_argument("value", type=float, help="refunded amount in EUR, e.g. 24.90")
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--wrong-secret", action="store_true", help="send an invalid secret to test the 401 path")
    args = parser.parse_args()

    base_url = os.environ.get("TAGGRS_URL")
    secret = os.environ.get("WEBHOOK_SECRET")
    if not base_url or not secret:
        print("Set TAGGRS_URL and WEBHOOK_SECRET environment variables first.", file=sys.stderr)
        return 2

    url = base_url.rstrip("/") + "/webhook/order"
    payload = {
        "type": "refund",
        "transaction_id": args.transaction_id,
        "value": args.value,
        "currency": args.currency,
    }
    headers = {"x-webhook-secret": "wrong" if args.wrong_secret else secret}
    # Optional: route this request into GTM server Preview (value from Preview → ⋮ → "Send requests manually").
    preview = os.environ.get("GTM_PREVIEW_HEADER")
    if preview:
        headers["X-Gtm-Server-Preview"] = preview

    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"POST {url} -> {response.status_code}")
    print(response.text)
    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
