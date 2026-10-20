-- =====================================================================
-- sql/seed_data.sql  —  Part 1, Task 2: load the three CSVs
-- Run from the repo root, after schema.sql:
--     sqlite3 mamaearth.db ".read sql/seed_data.sql"
-- Uses SQLite CLI dot-commands (.import), so it must be run with the
-- sqlite3 command-line tool, not a generic SQL client.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- Empty the tables first so the script is re-runnable without
-- duplicating rows. Child table (orders) first, as in schema.sql.
DELETE FROM orders;
DELETE FROM customers;
DELETE FROM products;

-- Load parents before the child, so every order's customer_id and
-- product_id already exist when the FOREIGN KEY check runs.
-- --skip 1 skips the header row; otherwise it is loaded as data.
.import --csv --skip 1 data/customers.csv customers
.import --csv --skip 1 data/products.csv products
.import --csv --skip 1 data/orders.csv orders

-- .import loads blank CSV cells as empty strings (''), not NULL.
-- Convert them so COUNT(rating) and COALESCE(discount_pct, 0) behave.
UPDATE orders SET discount_pct = NULL WHERE discount_pct = '';
UPDATE orders SET rating = NULL WHERE rating = '';

-- Verification: expect 45 / 16 / 180.
.headers on
.mode column
SELECT (SELECT COUNT(*) FROM customers) AS customers,
       (SELECT COUNT(*) FROM products)  AS products,
       (SELECT COUNT(*) FROM orders)    AS orders;

-- Verification: blanks are now real NULLs (expect 12 and 15, and no 'text' rows).
SELECT typeof(discount_pct) AS discount_type, COUNT(*) AS n
FROM orders GROUP BY typeof(discount_pct);
SELECT typeof(rating) AS rating_type, COUNT(*) AS n
FROM orders GROUP BY typeof(rating);
