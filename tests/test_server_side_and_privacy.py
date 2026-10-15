"""
Layer 2 – what actually leaves the browser.
Checks the requests sent to the tagging server (TAGGRS) and to Meta, per consent state.
Covers the privacy bugs found during the project so they can never silently come back.

Requires TAGGRS_HOST; skipped otherwise. Meta requests are captured but blocked (not delivered).
"""
import pytest

from conftest import BASE_URL, TAGGRS_HOST, buy, choose_consent, datalayer_events

pytestmark = pytest.mark.skipif(not TAGGRS_HOST, reason="set TAGGRS_HOST to run server-side tests")

PII_MARKERS = ("%40", "@", "x-fb-ud-em")


def key_carrying(hit, value):
    """Return the request parameter that carries `value` (GA4 may encode event params under different keys)."""
    return next((k for k, v in hit.items() if k != "_raw" and v == value), None)


def test_accept_all_sends_full_funnel_to_tagging_server(page, tracker):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    order_id = buy(page, BASE_URL)
    tracker.wait_for(lambda: tracker.ga4("purchase"), message="purchase hit at the tagging server")

    for name in ("view_item", "add_to_cart", "begin_checkout", "add_shipping_info", "add_payment_info", "purchase"):
        assert tracker.ga4(name), f"{name} never reached the tagging server"

    purchase = tracker.ga4("purchase")[-1]
    assert purchase.get("gcs") == "G111", f"expected full consent G111, got {purchase.get('gcs')}"
    assert purchase.get("ep.transaction_id") == order_id

    dl_purchase = next(e for e in datalayer_events(page) if e["event"] == "purchase")
    key = key_carrying(purchase, dl_purchase["event_id"])
    print(f"\n  event_id is sent to the server as parameter: {key}")
    assert key, f"event_id {dl_purchase['event_id']} not found in the purchase hit; keys: {sorted(purchase)}"
    assert purchase.get("uid", "").startswith("C-"), "user_id must be sent with analytics consent"
    assert purchase.get("ep.x-fb-ck-fbp", "").startswith("fb."), "_fbp must be forwarded for Meta CAPI matching"


def test_accept_all_meta_pixel_shares_event_id_with_server(page, tracker):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    buy(page, BASE_URL)
    tracker.wait_for(lambda: tracker.meta("Purchase") and tracker.ga4("purchase"),
                     message="Purchase at Meta Pixel and tagging server")

    dl_purchase = next(e for e in datalayer_events(page) if e["event"] == "purchase")
    pixel = tracker.meta("Purchase")[-1]
    server = tracker.ga4("purchase")[-1]
    assert pixel.get("eid") == dl_purchase["event_id"], "Pixel eventID must equal the dataLayer event_id"
    assert key_carrying(server, dl_purchase["event_id"]), \
        f"server hit must carry the dataLayer event_id {dl_purchase['event_id']}; keys: {sorted(server)}"
    assert not tracker.meta("SubscribedButtonClick"), "Meta automatic events must stay disabled"


def test_reject_all_blocks_marketing_and_identifiers(page, tracker):
    page.goto(BASE_URL)
    choose_consent(page, "Reject all")
    buy(page, BASE_URL)
    page.fill("#newsletter input[type=email]", "qa-lead@example.com")
    page.click("#newsletter button[type=submit]")
    tracker.wait_for(lambda: tracker.ga4("purchase"), message="cookieless purchase ping")

    assert not tracker.meta_hits, f"Meta Pixel must not fire without consent: {[h.get('ev') for h in tracker.meta_hits]}"
    for hit in tracker.ga4_hits:
        assert hit.get("gcs") == "G100", f"{hit['en']}: expected denied consent G100, got {hit.get('gcs')}"
        assert "uid" not in hit, f"{hit['en']}: user_id must not be sent without analytics consent"
        assert not any(k.startswith("ep.x-fb") for k in hit), f"{hit['en']}: Meta identifiers sent without consent"
        assert not any(m in hit["_raw"] for m in PII_MARKERS), f"{hit['en']}: possible email in request"
    ga_cookies = [c["name"] for c in page.context.cookies() if c["name"].startswith("_ga")]
    assert not ga_cookies, f"no _ga cookie may be set without analytics consent, found {ga_cookies}"


def test_no_email_reaches_ga4_payload_from_browser_without_marketing_consent(page, tracker):
    """Accept analytics only: GA4 runs, but no email and no Meta identifiers leave the browser."""
    page.goto(BASE_URL)
    page.get_by_role("button", name="Settings").first.click()
    page.get_by_text("Analytics", exact=True).first.wait_for()
    page.locator("#cc-main input[value=analytics]").check(force=True)
    page.get_by_role("button", name="Save settings").first.click()
    buy(page, BASE_URL)
    tracker.wait_for(lambda: tracker.ga4("purchase"), message="purchase hit")

    purchase = tracker.ga4("purchase")[-1]
    assert purchase.get("gcs") == "G101", f"expected analytics-only G101, got {purchase.get('gcs')}"
    assert "ep.x-fb-ud-em" not in purchase, "email must not be sent without marketing consent"
    assert not tracker.meta_hits, "Meta must not fire with analytics-only consent"