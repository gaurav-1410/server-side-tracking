"""
Diagnostic: what does the automated browser actually send?

Runs Accept all + a purchase three times:
  mode A = default headless Chromium
  mode B = headless Chromium that does not announce automation (no navigator.webdriver, normal user agent)
  mode C = mode B + service workers blocked (forces GA4 hits through normal page requests)
and prints every request to the tagging server and to Meta, including whether the request body was readable.

Usage (from the tests folder):
  $env:TAGGRS_HOST="4i5lfpssk0.onion.taggrs.io"
  python debug_requests.py
"""
import os
from urllib.parse import parse_qsl, urlparse

from playwright.sync_api import sync_playwright

from conftest import BASE_URL, TAGGRS_HOST, buy, choose_consent

NORMAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


def run(p, stealth, block_sw=False):
    args = ["--disable-blink-features=AutomationControlled"] if stealth else []
    browser = p.chromium.launch(headless=True, args=args)
    options = {"user_agent": NORMAL_UA} if stealth else {}
    if block_sw:
        options["service_workers"] = "block"
    context = browser.new_context(**options)
    log = []

    def on_request(req):
        host = urlparse(req.url).hostname or ""
        if host == TAGGRS_HOST or "facebook" in host:
            body = None
            try:
                body = req.post_data
            except Exception as exc:  # body not readable
                body = f"<unreadable: {exc}>"
            log.append((req.method, req.resource_type, req.url, body))

    context.on("request", on_request)
    page = context.new_page()
    page.goto(BASE_URL)
    print("  navigator.webdriver =", page.evaluate("navigator.webdriver"))
    choose_consent(page, "Accept all")
    order = buy(page, BASE_URL)
    page.wait_for_timeout(8000)  # give GA4 time to flush batched events
    print("  order:", order, "| fbq loaded:", page.evaluate("typeof window.fbq"))
    print("  dataLayer events on checkout page:",
          page.evaluate("dataLayer.filter(o=>o&&o.event&&!String(o.event).startsWith('gtm.')).map(o=>o.event)"))

    for method, rtype, url, body in log:
        u = urlparse(url)
        host = u.hostname
        if host == TAGGRS_HOST:
            url_events = [v for k, v in parse_qsl(u.query) if k == "en"]
            body_events = []
            if isinstance(body, str) and not body.startswith("<unreadable"):
                for line in body.split("\n"):
                    body_events += [v for k, v in parse_qsl(line) if k == "en"]
            body_info = "None" if body is None else (body if body.startswith("<unreadable") else f"{len(body)} chars")
            path = f" path={u.path}" if rtype == "document" else ""
            print(f"  TAGGRS {method:4} {rtype:9} url_events={url_events} body={body_info} body_events={body_events}{path}")
        else:
            ev = dict(parse_qsl(u.query)).get("ev")
            print(f"  META   {method:4} {rtype:9} {host}{u.path} ev={ev}")
    if not any("facebook" in (urlparse(x[2]).hostname or "") for x in log):
        print("  META   (no requests to any facebook domain)")
    browser.close()


if __name__ == "__main__":
    if not TAGGRS_HOST:
        raise SystemExit("Set TAGGRS_HOST first.")
    with sync_playwright() as p:
        print("\n=== Mode A: default headless ===")
        run(p, stealth=False)
        print("\n=== Mode B: headless without automation flags ===")
        run(p, stealth=True)
        print("\n=== Mode C: without automation flags + service workers blocked ===")
        run(p, stealth=True, block_sw=True)