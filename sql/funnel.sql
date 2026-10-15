-- =============================================================================
-- BQ2 / BQ4: Funnel step conversion, overall and per A/B variant.
-- Only consented users (user_pseudo_id present) – cookieless pings can't be linked into funnels.
-- =============================================================================
DECLARE start_date STRING DEFAULT '20261013';
DECLARE end_date   STRING DEFAULT FORMAT_DATE('%Y%m%d', CURRENT_DATE());

WITH steps AS (
  SELECT
    user_pseudo_id,
    event_name,
    -- variant the user was assigned to (sent on view_item, add_to_cart, select_item, purchase)
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'experiment_variant') AS variant
  FROM `coffee-house-tracking.analytics_XXXXXXXXX.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_date AND end_date
    AND user_pseudo_id IS NOT NULL
    AND event_name IN ('view_item', 'add_to_cart', 'begin_checkout', 'add_shipping_info',
                       'add_payment_info', 'purchase')
),
user_variant AS (
  SELECT user_pseudo_id, ANY_VALUE(variant) AS variant
  FROM steps WHERE variant IS NOT NULL GROUP BY user_pseudo_id
),
per_user AS (
  SELECT
    s.user_pseudo_id,
    IFNULL(v.variant, 'unknown') AS variant,
    LOGICAL_OR(event_name = 'view_item')         AS viewed,
    LOGICAL_OR(event_name = 'add_to_cart')       AS added,
    LOGICAL_OR(event_name = 'begin_checkout')    AS checkout,
    LOGICAL_OR(event_name = 'add_shipping_info') AS shipping,
    LOGICAL_OR(event_name = 'add_payment_info')  AS payment,
    LOGICAL_OR(event_name = 'purchase')          AS purchased
  FROM steps s LEFT JOIN user_variant v USING (user_pseudo_id)
  GROUP BY s.user_pseudo_id, variant
)
SELECT
  variant,
  COUNTIF(viewed)    AS users_view_item,
  COUNTIF(added)     AS users_add_to_cart,
  COUNTIF(checkout)  AS users_begin_checkout,
  COUNTIF(purchased) AS users_purchase,
  ROUND(SAFE_DIVIDE(COUNTIF(added), COUNTIF(viewed)) * 100, 1)      AS view_to_cart_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(checkout), COUNTIF(added)) * 100, 1)    AS cart_to_checkout_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(purchased), COUNTIF(checkout)) * 100, 1) AS checkout_to_purchase_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(purchased), COUNTIF(viewed)) * 100, 1)  AS overall_conversion_pct
FROM per_user
GROUP BY ROLLUP(variant)
ORDER BY variant NULLS LAST;
