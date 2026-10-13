// ============================================================================
// tracking.js – the ONLY file that talks to the dataLayer.
// Every function here maps 1:1 to a row in docs/tracking-plan (tab 2_Event_Map).
// Rule: the shop code calls these functions; it never pushes to dataLayer itself.
// ============================================================================

window.dataLayer = window.dataLayer || [];

const CURRENCY = 'EUR';

// ---------- helpers ---------------------------------------------------------

// One unique ID per event. Sent to GA4, the Meta/TikTok pixel AND the server,
// so Meta/TikTok can deduplicate browser + server copies of the same event.
function newEventId() {
  return (crypto.randomUUID && crypto.randomUUID()) ||
    Date.now() + '-' + Math.random().toString(16).slice(2);
}

// Convert a catalog product (+ quantity) into a GA4 "items" entry.
function toItem(product, quantity = 1, index) {
  const item = {
    item_id: product.item_id,
    item_name: product.item_name,
    item_category: product.item_category,
    price: product.price,
    quantity: quantity
  };
  if (index !== undefined) item.index = index;
  return item;
}

// value = sum of price x quantity, rounded to cents (avoids 0.1 + 0.2 issues).
function sumValue(items) {
  return Math.round(items.reduce((s, i) => s + i.price * i.quantity, 0) * 100) / 100;
}

// Ecommerce pushes MUST clear the previous ecommerce object first,
// otherwise GTM merges old items into the new event.
function pushEcommerce(eventName, ecommerce, extra = {}) {
  window.dataLayer.push({ ecommerce: null });
  window.dataLayer.push(Object.assign({
    event: eventName,
    event_id: newEventId(),
    ecommerce: ecommerce
  }, extra));
}

// ---------- A/B test (BQ4) --------------------------------------------------

const EXPERIMENT_ID = 'also_bought_v1';

function getVariant() {
  let v = Shop.storage.get('ab_' + EXPERIMENT_ID);
  if (!v) {
    v = Math.random() < 0.5 ? 'A_control' : 'B_also_bought';
    Shop.storage.set('ab_' + EXPERIMENT_ID, v);
  }
  return v;
}

// Fires once per user, the first time they are assigned a variant.
function trackExperimentImpression() {
  const variant = getVariant();
  if (Shop.storage.get('ab_seen_' + EXPERIMENT_ID)) return variant;
  Shop.storage.set('ab_seen_' + EXPERIMENT_ID, '1');
  window.dataLayer.push({
    event: 'experiment_impression',
    event_id: newEventId(),
    experiment_id: EXPERIMENT_ID,
    experiment_variant: variant
  });
  return variant;
}

// ---------- user identity (BQ6) ---------------------------------------------
// Internal customer ID – NOT personal data, so allowed in GA4 as user_id.
// The email is only placed in user_data; GTM must never forward it to GA4.

function getOrCreateUserId() {
  let id = Shop.storage.get('customer_id');
  if (!id) {
    id = 'C-' + Math.floor(10000 + Math.random() * 90000);
    Shop.storage.set('customer_id', id);
  }
  return id;
}

// ---------- events (one function per tracking-plan row) ---------------------

const Tracking = {
  viewItemList(products, listId, listName) {
    const items = products.map((p, i) => Object.assign(toItem(p, 1, i),
      { item_list_id: listId, item_list_name: listName }));
    pushEcommerce('view_item_list', { item_list_id: listId, item_list_name: listName, items });
  },

  selectItem(product, index, listId, listName) {
    const item = Object.assign(toItem(product, 1, index),
      { item_list_id: listId, item_list_name: listName });
    pushEcommerce('select_item',
      { item_list_id: listId, item_list_name: listName, items: [item] },
      { experiment_variant: getVariant() });
  },

  viewItem(product) {
    const items = [toItem(product)];
    pushEcommerce('view_item', { currency: CURRENCY, value: sumValue(items), items },
      { experiment_variant: getVariant() });
  },

  addToCart(product, quantity) {
    const items = [toItem(product, quantity)];
    pushEcommerce('add_to_cart', { currency: CURRENCY, value: sumValue(items), items },
      { experiment_variant: getVariant() });
  },

  beginCheckout(cartItems, coupon) {
    const ecommerce = { currency: CURRENCY, value: sumValue(cartItems), items: cartItems };
    if (coupon) ecommerce.coupon = coupon;
    pushEcommerce('begin_checkout', ecommerce);
  },

  addShippingInfo(cartItems, shippingTier) {
    pushEcommerce('add_shipping_info',
      { currency: CURRENCY, value: sumValue(cartItems), shipping_tier: shippingTier, items: cartItems });
  },

  addPaymentInfo(cartItems, paymentType) {
    pushEcommerce('add_payment_info',
      { currency: CURRENCY, value: sumValue(cartItems), payment_type: paymentType, items: cartItems });
  },

  // value = items total WITHOUT shipping, tax included (German prices are gross).
  // This definition is documented in the tracking plan.
  purchase(order) {
    pushEcommerce('purchase', {
      transaction_id: order.transaction_id,
      currency: CURRENCY,
      value: sumValue(order.items),
      tax: order.tax,
      shipping: order.shipping,
      items: order.items
    }, {
      experiment_variant: getVariant(),
      user_id: getOrCreateUserId(),
      user_data: { email: order.email }   // for Meta/TikTok only (hashed server-side)
    });
  },

  generateLead(email, leadSource) {
    window.dataLayer.push({
      event: 'generate_lead',
      event_id: newEventId(),
      lead_source: leadSource,
      user_id: getOrCreateUserId(),
      user_data: { email: email }         // for Meta/TikTok only (hashed server-side)
    });
  }
};
