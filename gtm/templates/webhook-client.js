// =============================================================================
// Order Webhook client – server-side GTM (sandboxed JavaScript)
//
// Receives order events (refunds) from the shop backend:
//   POST {data.path}   header: x-webhook-secret: <secret>
//   body: {"type":"refund","transaction_id":"T-1042","value":24.9,"currency":"EUR"}
//
// Responses:
//   200 ok | 400 invalid payload | 401 wrong/missing secret | 405 not POST
// Requests to any other path are NOT claimed, so the GA4 client still handles them.
// =============================================================================

const claimRequest = require('claimRequest');
const getRequestPath = require('getRequestPath');
const getRequestMethod = require('getRequestMethod');
const getRequestHeader = require('getRequestHeader');
const getRequestBody = require('getRequestBody');
const JSON = require('JSON');
const makeNumber = require('makeNumber');
const makeString = require('makeString');
const runContainer = require('runContainer');
const returnResponse = require('returnResponse');
const setResponseStatus = require('setResponseStatus');
const setResponseHeader = require('setResponseHeader');
const setResponseBody = require('setResponseBody');
const logToConsole = require('logToConsole');

// 1. Only handle our own path – everything else is left for other clients.
if (getRequestPath() !== data.path) {
  return;
}
claimRequest();

const respond = (status, body) => {
  setResponseStatus(status);
  setResponseHeader('content-type', 'application/json');
  setResponseBody(JSON.stringify(body));
  returnResponse();
};

// 2. Method check.
if (getRequestMethod() !== 'POST') {
  respond(405, {error: 'method_not_allowed'});
  return;
}

// 3. Authentication: shared secret in a header (never in the URL).
if (!data.secret || getRequestHeader('x-webhook-secret') !== data.secret) {
  logToConsole('Order Webhook: rejected request with missing or wrong secret');
  respond(401, {error: 'unauthorized'});
  return;
}

// 4. Validate payload. JSON.parse returns undefined for invalid JSON in the sandbox.
const body = JSON.parse(getRequestBody() || '');
if (!body || body.type !== 'refund' || !body.transaction_id) {
  respond(400, {error: 'invalid_payload', detail: 'type must be "refund" and transaction_id is required'});
  return;
}
const value = makeNumber(body.value);
if (!(value > 0)) {
  respond(400, {error: 'invalid_payload', detail: 'value must be a positive number'});
  return;
}

// 5. Build event data in GA4 naming, so the GA4 tag can forward it as-is.
const transactionId = makeString(body.transaction_id);
const eventData = {
  event_name: 'refund',
  // Refunds have no browser session; GA4 needs a client_id, so use the one the
  // backend stored with the order if available, otherwise a fixed backend ID.
  client_id: body.client_id ? makeString(body.client_id) : 'backend.refund',
  transaction_id: transactionId,
  value: value,
  currency: body.currency ? makeString(body.currency) : 'EUR',
  // Deterministic event_id: a retried webhook produces the same ID (idempotency key).
  event_id: 'refund-' + transactionId,
  event_source: 'order_webhook'
};
if (body.items) {
  eventData.items = body.items;
}

// 6. Run the container (tags fire on this event), then answer the backend.
runContainer(eventData, () => {
  respond(200, {status: 'ok', event: 'refund', transaction_id: transactionId});
});