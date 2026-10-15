-- =============================================================================
-- BQ7: Can we trust the purchase data? Data-quality checks on the GA4 export.
-- Each row is one check; status 'OK' or 'CHECK'. Replace the dataset name.
-- =============================================================================
DECLARE start_date STRING DEFAULT '20261013';
DECLARE end_date   STRING DEFAULT FORMAT_DATE('%Y%m%d', CURRENT_DATE());

WITH ev AS (
  SELECT
    event_name,
    user_pseudo_id,
    user_id,
    privacy_info.analytics_storage AS analytics_consent,
    COALESCE(
      ecommerce.transaction_id,
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'transaction_id')
    ) AS transaction_id,
    ARRAY_LENGTH(items) AS item_count
  FROM `coffee-house-tracking.analytics_XXXXXXXXX.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_date AND end_date
    AND event_name IN ('purchase', 'refund')
),
purchases AS (SELECT * FROM ev WHERE event_name = 'purchase'),
refunds   AS (SELECT * FROM ev WHERE event_name = 'refund'),
checks AS (
  SELECT 'purchases received' AS check_name,
         COUNT(*) AS value, 'info' AS expectation FROM purchases
  UNION ALL
  SELECT 'purchases without transaction_id',
         COUNTIF(transaction_id IS NULL), 'must be 0' FROM purchases
  UNION ALL
  SELECT 'duplicate purchase hits (same transaction_id)',
         (SELECT COUNT(*) FROM (SELECT transaction_id FROM purchases
                                WHERE transaction_id IS NOT NULL
                                GROUP BY transaction_id HAVING COUNT(*) > 1)),
         'must be 0'
  UNION ALL
  SELECT 'purchases without items',
         COUNTIF(IFNULL(item_count, 0) = 0), 'must be 0' FROM purchases
  UNION ALL
  SELECT 'refunds without a matching purchase',
         (SELECT COUNT(*) FROM refunds r
          WHERE NOT EXISTS (SELECT 1 FROM purchases p WHERE p.transaction_id = r.transaction_id)),
         'investigate if > 0'
  UNION ALL
  SELECT 'consent-denied purchases carrying user_id (privacy)',
         COUNTIF(analytics_consent = 'No' AND user_id IS NOT NULL), 'must be 0 (after fix)' FROM purchases
  UNION ALL
  SELECT 'consent-denied purchases (cookieless, no user_pseudo_id)',
         COUNTIF(analytics_consent = 'No'), 'info: share of unattributable revenue' FROM purchases
)
SELECT
  check_name,
  value,
  expectation,
  CASE
    WHEN expectation LIKE 'must be 0%' AND value > 0 THEN 'CHECK'
    WHEN expectation LIKE 'investigate%' AND value > 0 THEN 'CHECK'
    ELSE 'OK'
  END AS status
FROM checks;

-- Compare "purchases received" with the backend order count for the same period
-- (target: within 5%). Differences usually come from consent, ad blockers or
-- the thank-you page not loading – see docs/debug-runbook.md.
