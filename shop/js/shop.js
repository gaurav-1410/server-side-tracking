// ============================================================================
// shop.js – shop logic (cart, page rendering). Calls Tracking.* at the
// moments defined in the tracking plan. Look for "TRACKING:" comments.
// ============================================================================

const Shop = {
  storage: {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    remove(k) { try { localStorage.removeItem(k); } catch (e) {} }
  },

  findProduct(id) { return PRODUCTS.find(p => p.item_id === id); },

  // Cart is stored as [{item_id, quantity}]
  getCart() {
    try { return JSON.parse(Shop.storage.get('cart')) || []; } catch (e) { return []; }
  },
  saveCart(cart) { Shop.storage.set('cart', JSON.stringify(cart)); Shop.updateCartCount(); },

  addToCart(id, qty) {
    const cart = Shop.getCart();
    const line = cart.find(l => l.item_id === id);
    if (line) line.quantity += qty; else cart.push({ item_id: id, quantity: qty });
    Shop.saveCart(cart);
  },

  // Cart lines as GA4 items (used by checkout events)
  cartItems() {
    return Shop.getCart().map(l => toItem(Shop.findProduct(l.item_id), l.quantity));
  },

  updateCartCount() {
    const n = Shop.getCart().reduce((s, l) => s + l.quantity, 0);
    document.querySelectorAll('[data-cart-count]').forEach(el => el.textContent = n);
  },

  euro(n) { return n.toFixed(2).replace('.', ',') + ' €'; },

  productCard(p, index, listId, listName) {
    const a = document.createElement('a');
    a.className = 'card';
    a.href = 'product.html?id=' + encodeURIComponent(p.item_id);
    a.innerHTML = `<div class="thumb">${p.item_category}</div>
      <h3>${p.item_name}</h3><p class="price">${Shop.euro(p.price)}</p>`;
    // TRACKING: select_item when a product card is clicked
    a.addEventListener('click', () => Tracking.selectItem(p, index, listId, listName));
    return a;
  }
};

// ---------- pages -----------------------------------------------------------

function initListPage() {
  const grid = document.getElementById('product-grid');
  PRODUCTS.forEach((p, i) => grid.appendChild(Shop.productCard(p, i, 'all_products', 'All products')));
  // TRACKING: view_item_list once the list is rendered
  Tracking.viewItemList(PRODUCTS, 'all_products', 'All products');
}

function initProductPage() {
  const id = new URLSearchParams(location.search).get('id');
  const p = Shop.findProduct(id) || PRODUCTS[0];
  document.title = p.item_name + ' – Coffee House';
  document.getElementById('p-name').textContent = p.item_name;
  document.getElementById('p-price').textContent = Shop.euro(p.price);
  document.getElementById('p-desc').textContent = p.description;
  document.getElementById('p-thumb').textContent = p.item_category;

  // TRACKING: experiment_impression (first time only), then view_item
  const variant = trackExperimentImpression();
  Tracking.viewItem(p);

  document.getElementById('add-to-cart').addEventListener('click', () => {
    const qty = Math.max(1, parseInt(document.getElementById('qty').value, 10) || 1);
    Shop.addToCart(p.item_id, qty);
    // TRACKING: add_to_cart
    Tracking.addToCart(p, qty);
    const msg = document.getElementById('added-msg');
    msg.hidden = false;
  });

  // Variant B shows "Customers also bought" (BQ4)
  if (variant === 'B_also_bought') {
    const section = document.getElementById('also-bought');
    const grid = document.getElementById('also-bought-grid');
    section.hidden = false;
    (ALSO_BOUGHT[p.item_id] || []).map(Shop.findProduct).forEach((rp, i) =>
      grid.appendChild(Shop.productCard(rp, i, 'also_bought', 'Customers also bought')));
  }
}

function initCartPage() {
  const list = document.getElementById('cart-lines');
  const cart = Shop.getCart();
  if (!cart.length) {
    list.innerHTML = '<p>Your cart is empty. <a href="index.html">Go shopping</a></p>';
    document.getElementById('checkout-btn').hidden = true;
    return;
  }
  cart.forEach(l => {
    const p = Shop.findProduct(l.item_id);
    const row = document.createElement('div');
    row.className = 'cart-line';
    row.innerHTML = `<span>${p.item_name} × ${l.quantity}</span><span>${Shop.euro(p.price * l.quantity)}</span>`;
    list.appendChild(row);
  });
  document.getElementById('cart-total').textContent = Shop.euro(sumValue(Shop.cartItems()));

  document.getElementById('checkout-btn').addEventListener('click', () => {
    // TRACKING: begin_checkout, then go to checkout page
    Tracking.beginCheckout(Shop.cartItems());
    location.href = 'checkout.html';
  });
}

function initCheckoutPage() {
  const items = Shop.cartItems();
  if (!items.length) { location.href = 'index.html'; return; }
  document.getElementById('checkout-total').textContent = Shop.euro(sumValue(items));

  const stepShipping = document.getElementById('step-shipping');
  const stepPayment = document.getElementById('step-payment');
  const stepDone = document.getElementById('step-done');

  stepShipping.addEventListener('submit', e => {
    e.preventDefault();
    const tier = stepShipping.querySelector('input[name="shipping"]:checked').value;
    Shop.storage.set('shipping_tier', tier);
    // TRACKING: add_shipping_info
    Tracking.addShippingInfo(items, tier);
    stepShipping.hidden = true;
    stepPayment.hidden = false;
  });

  stepPayment.querySelectorAll('input[name="payment"]').forEach(r =>
    r.addEventListener('change', () => {
      // TRACKING: add_payment_info when a payment method is chosen
      Tracking.addPaymentInfo(items, r.value);
    }, { once: true }));

  stepPayment.addEventListener('submit', e => {
    e.preventDefault();
    const tier = Shop.storage.get('shipping_tier') || 'standard';
    const shipping = tier === 'express' ? 9.90 : 4.90;
    const value = sumValue(items);
    const order = {
      transaction_id: 'T-' + Date.now(),           // unique per order (BQ7)
      items: items,
      shipping: shipping,
      tax: Math.round(value / 1.19 * 0.19 * 100) / 100,  // 19% VAT included in gross price
      email: document.getElementById('email').value.trim()
    };
    // TRACKING: purchase on the thank-you state
    Tracking.purchase(order);
    Shop.saveCart([]);
    stepPayment.hidden = true;
    stepDone.hidden = false;
    document.getElementById('order-id').textContent = order.transaction_id;
  });
}

function initNewsletter() {
  const form = document.getElementById('newsletter');
  if (!form) return;
  form.addEventListener('submit', e => {
    e.preventDefault();
    const email = form.querySelector('input[type="email"]').value.trim();
    if (!email) return;
    // TRACKING: generate_lead
    Tracking.generateLead(email, 'footer_newsletter');
    form.innerHTML = '<p>Thanks for subscribing!</p>';
  });
}

document.addEventListener('DOMContentLoaded', () => {
  Shop.updateCartCount();
  initNewsletter();
  const page = document.body.dataset.page;
  if (page === 'list') initListPage();
  if (page === 'product') initProductPage();
  if (page === 'cart') initCartPage();
  if (page === 'checkout') initCheckoutPage();
});
