-- =====================================================================
-- sql/reports.sql  —  Part 1, Task 3: nine business reports (a–i)
-- Run from the repo root, after schema.sql and seed_data.sql:
--     sqlite3 mamaearth.db ".read sql/reports.sql"
-- All queries run on the RAW loaded data (duplicates, NULLs and mixed
-- casing still present). The output of each query is pasted above it.
-- =====================================================================

.headers on
.mode column

-- ---------------------------------------------------------------------
-- (a) Order totals: order count, total revenue, average order value.
-- Revenue per row = quantity * price * (1 - discount_pct / 100).
-- NULL discount is treated as 0% via COALESCE.
-- Divide by 100.0, not 100: discount_pct is an INT, and INT / INT in
-- SQLite is integer division (30 / 100 = 0), which would ignore discounts.
--
-- Output:
-- total_orders  total_revenue  avg_order_value
-- ------------  -------------  ---------------
--          180        99860.2           554.78
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;

-- ---------------------------------------------------------------------
-- (b) COUNT(*) vs COUNT(column).
-- COUNT(*) counts rows; COUNT(rating) skips NULLs. The difference is the
-- number of orders with no rating yet.
--
-- Output:
-- total_orders  rated_orders  unrated_orders
-- ------------  ------------  --------------
--          180           165              15
-- ---------------------------------------------------------------------
SELECT COUNT(*)                 AS total_orders,
       COUNT(rating)            AS rated_orders,
       COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;

-- ---------------------------------------------------------------------
-- (c) Customers with zero orders, found two independent ways.
-- Method 1: LEFT JOIN keeps every customer; customers with no orders get
-- NULL order columns, so COUNT(o.order_id) = 0 for them.
--
-- Output:
-- customer_id   name   order_count
-- -----------  ------  -----------
-- C045         Vihaan            0
-- ---------------------------------------------------------------------
SELECT c.customer_id, c.name, COUNT(o.order_id) AS order_count
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- Method 2: NOT IN cross-check. Must return the same customer as Method 1.
-- (Safe here because orders.customer_id is NOT NULL; a NULL inside the
-- NOT IN list would make the query return no rows at all.)
--
-- Output:
-- customer_id   name
-- -----------  ------
-- C045         Vihaan
-- ---------------------------------------------------------------------
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- ---------------------------------------------------------------------
-- (d) Return rate by city, keeping only cities above 20%.
-- returned is 0/1, so SUM(returned) = number of returned orders.
-- 100.0 (not 100) keeps the division decimal.
-- WHERE filters rows before grouping; HAVING filters groups after, which
-- is why the return-rate filter must go in HAVING.
--
-- Output:
--   city     total_orders  returned_orders  return_rate_pct
-- ---------  ------------  ---------------  ---------------
-- Jaipur               19                8             42.1
-- Lucknow              49               15             30.6
-- Bangalore            33                8             24.2
-- ---------------------------------------------------------------------
SELECT c.city,
       COUNT(*)                                     AS total_orders,
       SUM(o.returned)                              AS returned_orders,
       ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- ---------------------------------------------------------------------
-- (e) Top customers by total spend, using ORDER BY + LIMIT / OFFSET.
-- Tie-break: customer_id ASC makes the order deterministic when two
-- customers have equal spend, so LIMIT/OFFSET pages never shift between runs.
--
-- Top 5 (LIMIT 5) output:
-- customer_id   name    total_spend
-- -----------  -------  -----------
-- C043         Reyansh      12920.0
-- C026         Isha          8371.6
-- C008         Meera         4564.6
-- C011         Arjun         4111.0
-- C042         Sanya         3785.0
-- ---------------------------------------------------------------------
SELECT c.customer_id,
       c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- Ranks 3–5 (LIMIT 3 OFFSET 2): skip the first 2 rows, return the next 3.
-- Must equal the last three rows of the top-5 result, in the same order.
--
-- Output:
-- customer_id  name   total_spend
-- -----------  -----  -----------
-- C008         Meera       4564.6
-- C011         Arjun       4111.0
-- C042         Sanya       3785.0
-- ---------------------------------------------------------------------
SELECT c.customer_id,
       c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- ---------------------------------------------------------------------
-- (f) Order count and revenue by product category (three-table JOIN).
-- Only orders + products are strictly needed; customers is joined to
-- confirm the three-way join compiles cleanly.
--
-- Output:
--   category    order_count  category_revenue
-- ------------  -----------  ----------------
-- Haircare               54           44956.1
-- Skincare               60           27346.0
-- Babycare               30           16805.0
-- PersonalCare           36           10753.1
-- ---------------------------------------------------------------------
SELECT p.category,
       COUNT(*) AS order_count,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p  ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

-- ---------------------------------------------------------------------
-- (g) LIKE pattern match: customers whose name starts with 'A'.
-- % is a wildcard for "any characters (including none)".
--
-- Output (10 rows):
-- customer_id   name
-- -----------  ------
-- C001         Aarav
-- C003         Aditi
-- C004         Ananya
-- C011         Arjun
-- C021         Aryan
-- C030         Anika
-- C031         Aditya
-- C036         Aisha
-- C041         Ayaan
-- C044         Aria
-- ---------------------------------------------------------------------
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;

-- ---------------------------------------------------------------------
-- (h) DISTINCT: the different acquisition sources used across customers.
--
-- Output (4 values):
-- acquisition_source
-- ------------------
-- Ad
-- Organic
-- Referral
-- Social
-- ---------------------------------------------------------------------
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;

-- ---------------------------------------------------------------------
-- (i) ALTER TABLE + UPDATE with CASE: add loyalty_tier.
-- Gold for tier-1 cities, Silver otherwise. No WHERE clause, so every
-- row gets a value.
-- NOTE: this changes the table structure, so this file is meant to be
-- run once on a freshly built database (schema.sql -> seed_data.sql ->
-- reports.sql). Re-running it alone fails with "duplicate column name".
-- ---------------------------------------------------------------------
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

-- Check output:
-- loyalty_tier  COUNT(*)
-- ------------  --------
-- Gold                28
-- Silver              17
SELECT loyalty_tier, COUNT(*)
FROM customers
GROUP BY loyalty_tier;
