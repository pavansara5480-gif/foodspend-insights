-- FoodSpend Insights: analysis queries (portable MySQL 8 / SQLite SQL).
-- Each query starts with "-- name: <id>" so analysis/scripts/validate_sql.py can run it and compare the
-- result with the pandas implementation in backend/foodspend_core.
-- Spending is always aggregated at ORDER level to avoid multiplying order charges by the number of items.

-- name: total_spending
-- Total spending = sum of final totals for real transactions (home-meal ingredient estimates excluded).
SELECT ROUND(SUM(final_total_inr), 2) AS total_spending_inr,
       COUNT(*)                        AS transactions
FROM orders
WHERE record_type <> 'home_meal';

-- name: spending_components
SELECT ROUND(SUM(items_subtotal_inr), 2) AS items_subtotal,
       ROUND(SUM(order_discount_inr), 2) AS discounts,
       ROUND(SUM(tax_inr), 2)            AS tax,
       ROUND(SUM(delivery_fee_inr), 2)   AS delivery_fees,
       ROUND(SUM(other_charges_inr), 2)  AS other_charges
FROM orders
WHERE record_type <> 'home_meal';

-- name: monthly_spending
SELECT SUBSTR(CAST(order_date AS CHAR), 1, 7) AS month,
       ROUND(SUM(final_total_inr), 2)          AS spending_inr,
       COUNT(*)                                AS transactions
FROM orders
WHERE record_type <> 'home_meal'
GROUP BY SUBSTR(CAST(order_date AS CHAR), 1, 7)
ORDER BY month;

-- name: spending_by_meal_type
SELECT meal_type, ROUND(SUM(final_total_inr), 2) AS spending_inr, COUNT(*) AS transactions
FROM orders
WHERE record_type <> 'home_meal'
GROUP BY meal_type
ORDER BY spending_inr DESC;

-- name: spending_by_vendor
-- orders -> vendors is many-to-one, so this join cannot duplicate order totals.
SELECT v.vendor_name, ROUND(SUM(o.final_total_inr), 2) AS spending_inr, COUNT(*) AS transactions
FROM orders o
JOIN vendors v ON v.vendor_id = o.vendor_id
WHERE o.record_type <> 'home_meal'
GROUP BY v.vendor_name
ORDER BY spending_inr DESC;

-- name: spending_by_category
-- Item line totals by food category, plus order-level charges as their own row so the rows reconcile.
SELECT f.category AS label, ROUND(SUM(oi.line_total_inr), 2) AS spending_inr
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN foods f ON f.food_id = oi.food_id
WHERE o.record_type <> 'home_meal'
GROUP BY f.category
UNION ALL
SELECT 'Order-level charges (tax + fees - discounts)',
       ROUND(SUM(tax_inr + delivery_fee_inr + other_charges_inr - order_discount_inr), 2)
FROM orders
WHERE record_type <> 'home_meal';

-- name: naive_join_duplication
-- WRONG on purpose: summing order totals after joining to items counts multi-item orders more than once.
SELECT ROUND(SUM(o.final_total_inr), 2) AS naive_total_inr
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.record_type <> 'home_meal';

-- name: top_purchased_foods
-- Purchase events = number of distinct transactions containing the food (not proof of liking).
SELECT f.food_name, COUNT(DISTINCT oi.order_id) AS purchase_events, ROUND(SUM(oi.line_total_inr), 2) AS spending_inr
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN foods f ON f.food_id = oi.food_id
WHERE o.record_type <> 'home_meal'
GROUP BY f.food_name
ORDER BY purchase_events DESC, spending_inr DESC
LIMIT 10;

-- name: average_daily_logged_intake
-- consumed nutrient = quantity x serving_size / basis_quantity x value x portion_consumed.
-- "1.0 *" forces decimal arithmetic (SQLite stores whole numbers as INTEGER and would truncate).
-- Unknown consumption (portion NULL) and grocery purchases are excluded; days without meals are not averaged.
SELECT ROUND(AVG(kcal), 1) AS calories_kcal, ROUND(AVG(protein), 1) AS protein_g, COUNT(*) AS days_logged
FROM (
    SELECT o.order_date,
           SUM(1.0 * oi.quantity * oi.serving_size / n.basis_quantity * n.calories_kcal * oi.portion_consumed) AS kcal,
           SUM(1.0 * oi.quantity * oi.serving_size / n.basis_quantity * n.protein_g * oi.portion_consumed)    AS protein
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    JOIN food_nutrition n ON n.food_id = oi.food_id
    WHERE o.record_type <> 'grocery_purchase'
    GROUP BY o.order_date
) daily;

-- name: unknown_fiber_items
SELECT COUNT(*) AS meal_items_unknown_fiber
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN food_nutrition n ON n.food_id = oi.food_id
WHERE o.record_type <> 'grocery_purchase' AND n.fiber_g IS NULL;

-- name: preference_by_food
SELECT f.food_name, COUNT(*) AS n_ratings, ROUND(AVG(fb.rating), 2) AS mean_rating
FROM food_feedback fb
JOIN foods f ON f.food_id = fb.food_id
GROUP BY f.food_name
ORDER BY n_ratings DESC, mean_rating DESC;

-- name: rating_distribution
SELECT rating, COUNT(*) AS feedback_records FROM food_feedback GROUP BY rating ORDER BY rating;

-- name: weight_first_last
SELECT MIN(measurement_date) AS first_date, MAX(measurement_date) AS last_date, COUNT(*) AS readings
FROM health_measurements
WHERE indicator = 'weight';
