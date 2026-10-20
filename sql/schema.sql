-- =====================================================================
-- sql/schema.sql  —  Part 1, Task 1: table definitions
-- Run:  sqlite3 mamaearth.db ".read sql/schema.sql"
-- =====================================================================

-- SQLite ignores FOREIGN KEY rules unless this is switched on.
PRAGMA foreign_keys = ON;

-- Drop old tables so this script can be re-run from scratch.
-- Child table (orders) goes first, because it references the other two.
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;

-- One row per customer.
CREATE TABLE customers (
    customer_id        VARCHAR(10) PRIMARY KEY,
    name               VARCHAR(50) NOT NULL,
    city               VARCHAR(50) NOT NULL,
    city_tier          INT         NOT NULL,
    signup_date        DATE        NOT NULL,
    acquisition_source VARCHAR(20) NOT NULL
);

-- One row per product in the catalogue. Price is in INR.
CREATE TABLE products (
    product_id   VARCHAR(10)   PRIMARY KEY,
    product_name VARCHAR(100)  NOT NULL,
    category     VARCHAR(30)   NOT NULL,
    price        DECIMAL(10,2) NOT NULL
);

-- One row per order line.
-- discount_pct and rating are deliberately nullable: an order can have
-- no promo code or no rating yet, and NULL is the honest way to record that.
CREATE TABLE orders (
    order_id       VARCHAR(10) PRIMARY KEY,
    customer_id    VARCHAR(10) NOT NULL,
    product_id     VARCHAR(10) NOT NULL,
    order_date     DATE        NOT NULL,
    quantity       INT         NOT NULL,
    discount_pct   INT,
    payment_method VARCHAR(10) NOT NULL,
    rating         INT,
    returned       INT         NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
);
