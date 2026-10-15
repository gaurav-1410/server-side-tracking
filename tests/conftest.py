"""
Shared fixtures for the tracking QA suite.

Environment variables:
  BASE_URL     shop URL (default: the live GitHub Pages site)
  TAGGRS_HOST  host of the tagging server, e.g. 4i5lfpssk0.onion.taggrs.io
               (network tests are skipped when it is not set)
  HEADED=1     show the browser window while testing
"""
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlparse

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "https://gaurav-1410.github.io/server-side-tracking/").rstrip("/") + "/"
TAGGRS_HOST = os.environ.get("TAGGRS_HOST", "").strip().replace("https://", "").rstrip("/")


@dataclass
class Tracker:
    """Collects every tracking request the browser sends, across page navigations."""
    ga4_hits: list = field(default_factory=list)   # one dict per GA4 event that reached the tagging server
    meta_hits: list = field(default_factory=list)  # one dict per Meta Pixel request

    def on_request(self, request):
        url = urlparse(request.url)
        if TAGGRS_HOST and url.hostname == TAGGRS_HOST and "/g/collect" in url.path:
            shared = dict(parse_qsl(url.query))
            body = request.post_data or ""
            lines = [line for line in body.split("\n") if line.strip()] or [""]
            for line in lines:  # GA4 batches several events into one request body
                event = dict(shared)
                event.update(dict(parse_qsl(line)))
                if "en" in event:
                    event["_raw"] = request.url + "\n" + line
                    self.ga4_hits.append(event)
        elif url.hostname and url.hostname.endswith("facebook.com") and url.path.startswith("/tr"):
            self.meta_hits.append(dict(parse_qsl(url.query)) | {"_raw": request.url})

    def ga4(self, name):
        return [h for h in self.ga4_hits if h.get("en") == name]

    def meta(self, name):
        return [h for h in self.meta_hits if h.get("ev") == name]

    def wait_for(self, predicate, timeout=10.0, message="condition"):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.25)
        raise AssertionError(f"Timed out waiting for {message}")


# A normal desktop Chrome user agent. Headless Chromium otherwise announces "HeadlessChrome",
# and the Meta Pixel silently drops events from browsers it detects as automated.
NORMAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=os.environ.get("HEADED") != "1",
            # Removes navigator.webdriver = true (second automation signal the Pixel checks).
            args=["--disable-blink-features=AutomationControlled"],
        )
        yield b
        b.close()


@pytest.fixture
def tracker():
    return Tracker()


@pytest.fixture
def page(browser, tracker):
    """A fresh browser context per test = a brand-new visitor with no cookies or consent."""
    context = browser.new_context(
        user_agent=NORMAL_UA,
        # The Google tag sends hits to the server container through a service worker
        # (/_/service_worker/.../sw_iframe.html). Playwright does not observe service-worker
        # requests, so we block service workers and the tag falls back to normal page requests.
        # The tracking payload is identical; only the transport differs.
        service_workers="block",
    )
    context.on("request", tracker.on_request)
    # Capture Meta Pixel requests but don't deliver them: keeps QA runs out of the ad account.
    context.route(re.compile(r"https://([a-z]+\.)?facebook\.com/tr.*"), lambda route: route.abort())
    pg = context.new_page()
    yield pg
    pg.wait_for_timeout(500)
    context.close()


# ---------- helpers used by the tests ----------

def datalayer_events(page):
    """All dataLayer objects that have an 'event' key, in push order (current page only)."""
    return page.evaluate("(window.dataLayer || []).filter(o => o && o.event && !String(o.event).startsWith('gtm.'))"
                         ".map(o => JSON.parse(JSON.stringify(o)))")


def consent_commands(page):
    return page.evaluate(
        "(window.dataLayer || []).filter(o => o && o[0] === 'consent').map(o => [o[1], JSON.parse(JSON.stringify(o[2]))])")


def choose_consent(page, choice):
    """choice: 'Accept all' or 'Reject all'."""
    button = page.get_by_role("button", name=choice).first
    button.wait_for(state="visible", timeout=10000)
    button.click()
    page.wait_for_timeout(300)


def buy(page, base_url, product_id="SKU-101", qty=2, email="qa-test@example.com"):
    """Runs the full funnel and returns the order number shown on the thank-you step."""
    page.goto(base_url + "product.html?id=" + product_id)
    page.fill("#qty", str(qty))
    page.click("#add-to-cart")
    page.goto(base_url + "cart.html")
    page.click("#checkout-btn")
    page.wait_for_url("**/checkout.html")
    page.click("#step-shipping button[type=submit]")
    page.check("input[name=payment][value=paypal]")
    page.fill("#email", email)
    page.click("#step-payment button[type=submit]")
    page.wait_for_selector("#step-done", state="visible")
    return page.text_content("#order-id").strip()