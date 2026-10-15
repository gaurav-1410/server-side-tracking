"""
Layer 1 – dataLayer contract.
Checks that the website pushes exactly what the tracking plan (docs/tracking-plan) specifies.
These tests need no tagging server and run against any copy of the shop.
"""
import re

import pytest

from conftest import BASE_URL, buy, choose_consent, consent_commands, datalayer_events

UUID = re.compile(r"^[0-9a-f-]{16,}$")
REQUIRED_ECOMMERCE = {"currency", "value", "items"}
ITEM_KEYS = {"item_id", "item_name", "price", "quantity"}


def assert_valid_ecommerce(event):
    ecom = event["ecommerce"]
    assert REQUIRED_ECOMMERCE <= ecom.keys(), f"{event['event']}: missing {REQUIRED_ECOMMERCE - ecom.keys()}"
    assert ecom["currency"] == "EUR", f"{event['event']}: currency must be ISO 4217 'EUR'"
    assert ecom["items"], f"{event['event']}: items must not be empty"
    for item in ecom["items"]:
        assert ITEM_KEYS <= item.keys(), f"{event['event']}: item missing {ITEM_KEYS - item.keys()}"
        assert re.match(r"^SKU-\d{3}$", item["item_id"]), f"item_id format: {item['item_id']}"
    expected = round(sum(i["price"] * i["quantity"] for i in ecom["items"]), 2)
    assert ecom["value"] == expected, f"{event['event']}: value {ecom['value']} != sum(price*qty) {expected}"


def test_consent_defaults_are_denied_before_any_choice(page):
    page.goto(BASE_URL)
    commands = consent_commands(page)
    assert commands and commands[0][0] == "default", "consent default must be the first consent command"
    default = commands[0][1]
    for key in ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"):
        assert default[key] == "denied", f"{key} must default to denied"
    # The banner renders shortly after load, so wait for it instead of checking instantly.
    page.get_by_role("button", name="Accept all").first.wait_for(state="visible", timeout=10000)


@pytest.mark.parametrize("choice, expected", [("Accept all", "granted"), ("Reject all", "denied")])
def test_consent_update_matches_choice(page, choice, expected):
    page.goto(BASE_URL)
    choose_consent(page, choice)
    updates = [c[1] for c in consent_commands(page) if c[0] == "update"]
    assert updates, "a consent update must be sent after the banner choice"
    assert updates[-1]["analytics_storage"] == expected
    assert updates[-1]["ad_storage"] == expected


def test_product_page_events(page):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    page.goto(BASE_URL + "product.html?id=SKU-201")
    page.fill("#qty", "3")
    page.click("#add-to-cart")
    events = datalayer_events(page)
    names = [e["event"] for e in events]
    assert names.count("view_item") == 1, f"view_item must fire exactly once, got {names}"
    assert names.count("add_to_cart") == 1, f"add_to_cart must fire exactly once, got {names}"
    add = next(e for e in events if e["event"] == "add_to_cart")
    assert_valid_ecommerce(add)
    assert add["ecommerce"]["items"][0]["quantity"] == 3
    assert add["ecommerce"]["value"] == 147.0  # 3 x 49.00 hand grinder


def test_ecommerce_object_is_cleared_before_each_push(page):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    page.goto(BASE_URL + "product.html?id=SKU-101")
    page.click("#add-to-cart")
    raw = page.evaluate("window.dataLayer.map(o => JSON.parse(JSON.stringify(o)))")
    for i, obj in enumerate(raw):
        if isinstance(obj, dict) and obj.get("ecommerce"):
            assert raw[i - 1] == {"ecommerce": None}, f"{obj.get('event')} not preceded by {{ecommerce: null}}"


def test_purchase_contract(page):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    order_id = buy(page, BASE_URL, product_id="SKU-102", qty=2)
    events = datalayer_events(page)
    names = [e["event"] for e in events]
    for name in ("add_shipping_info", "add_payment_info", "purchase"):
        assert names.count(name) == 1, f"{name} must fire exactly once on checkout, got {names}"

    purchase = next(e for e in events if e["event"] == "purchase")
    assert_valid_ecommerce(purchase)
    assert purchase["ecommerce"]["transaction_id"] == order_id, "transaction_id must match the order number shown"
    assert re.match(r"^T-\d+$", order_id)
    assert purchase["ecommerce"]["value"] == 25.8  # 2 x 12.90 filter beans, excl. shipping
    assert UUID.match(purchase["event_id"]), "purchase needs an event_id for Meta deduplication"
    assert re.match(r"^C-\d{5}$", purchase["user_id"])


def test_event_ids_are_unique(page):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    buy(page, BASE_URL)
    ids = [e["event_id"] for e in datalayer_events(page) if "event_id" in e]
    assert len(ids) == len(set(ids)), "every event needs its own event_id"


def test_newsletter_lead(page):
    page.goto(BASE_URL)
    choose_consent(page, "Accept all")
    page.fill("#newsletter input[type=email]", "qa-lead@example.com")
    page.click("#newsletter button[type=submit]")
    leads = [e for e in datalayer_events(page) if e["event"] == "generate_lead"]
    assert len(leads) == 1
    assert leads[0]["lead_source"] == "footer_newsletter"
    assert UUID.match(leads[0]["event_id"])
