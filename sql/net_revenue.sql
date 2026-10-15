-- =============================================================================
-- BQ5: Net revenue after refunds (GA4 BigQuery export)
-- Replace the dataset name. Refunds arrive server-side via the Order Webhook client.
-- =============================================================================
DECLARE start_date STRING DEFAULT '20261013';
DECLARE end_date   STRING DEFAULT FORMAT_DATE('%Y%m%d', CURRENT_DATE());

WITH orders AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS day,
    event_name,
    COALESCE(
      ecommerce.transaction_id,
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'transaction_id')
    ) AS transaction_id,
    COALESCE(
      CASE WHEN event_name = 'purchase' THEN ecommerce.purchase_revenue END,
      CASE WHEN event_name = 'refund'   THEN ecommerce.refund_value END,
      (SELECT COALESCE(value.double_value, value.float_value, CAST(value.int_value AS FLOAT64))
         FROM UNNEST(event_params) WHERE key = 'value')
    ) AS amount
  FROM `coffee-house-tracking.analytics_XXXXXXXXX.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_date AND end_date
    AND event_name IN ('purchase', 'refund')
),
-- One row per transaction: protects against duplicate purchase hits inflating revenue.
per_transaction AS (
  SELECT
    transaction_id,
    MIN(IF(event_name = 'purchase', day, NULL))    AS purchase_day,
    MAX(IF(event_name = 'purchase', amount, 0))    AS gross,
    SUM(IF(event_name = 'refund', amount, 0))      AS refunded
  FROM orders
  WHERE transaction_id IS NOT NULL
  GROUP BY transaction_id
)
SELECT
  purchase_day,
  COUNT(*)                                   AS orders,
  ROUND(SUM(gross), 2)                       AS gross_revenue,
  ROUND(SUM(refunded), 2)                    AS refunds,
  ROUND(SUM(gross) - SUM(refunded), 2)       AS net_revenue,
  ROUND(SAFE_DIVIDE(SUM(refunded), SUM(gross)) * 100, 1) AS refund_rate_pct
FROM per_transaction
WHERE purchase_day IS NOT NULL               -- refunds without a known purchase: see reconcile_purchases.sql
GROUP BY purchase_day
ORDER BY purchase_day;
