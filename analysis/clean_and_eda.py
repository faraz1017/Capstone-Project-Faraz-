"""
analysis/clean_and_eda.py — Part 2: data cleaning and exploratory analysis.

Runs on the raw CSVs in data/ (not on the SQLite database), so Part 1
and Part 2 can be run in either order.

Run from the repo root:
    python analysis/clean_and_eda.py
"""

import json
from pathlib import Path

import pandas as pd

# Build paths from this file's location, so the script works no matter
# which folder it is launched from.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Show every column when printing tables, instead of hiding some with "...".
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 120)


def section(title):
    """Print a clear heading so each task's output is easy to find."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------
# Task 1 — Load and inspect
# ---------------------------------------------------------------------
section("Task 1 - Load and inspect")

customers = pd.read_csv(DATA_DIR / "customers.csv")
products = pd.read_csv(DATA_DIR / "products.csv")
orders = pd.read_csv(DATA_DIR / "orders.csv")

print("customers shape:", customers.shape)
print("products shape: ", products.shape)
print("orders shape (raw, before any cleaning):", orders.shape)

print("\nFirst 5 orders:")
print(orders.head())

print("\nColumn data types in orders:")
print(orders.dtypes)

print("\nMissing values per column in orders:")
print(orders.isnull().sum())

# ---------------------------------------------------------------------
# Task 2 — Standardise payment_method casing
# ---------------------------------------------------------------------
section("Task 2 - Standardise payment_method casing")

raw_methods = orders["payment_method"].unique()
print(f"Before: {len(raw_methods)} distinct raw values -> {list(raw_methods)}")

# strip() removes stray spaces; upper() makes 'cod', 'Cod', 'COD' identical.
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()

clean_methods = orders["payment_method"].unique()
print(f"After:  {len(clean_methods)} distinct values -> {list(clean_methods)}")

print("\nOrder count per payment method (all 180 rows):")
print(orders["payment_method"].value_counts())

# ---------------------------------------------------------------------
# Task 3 - Remove duplicate orders
# ---------------------------------------------------------------------
section("Task 3 - Remove duplicate orders")

# The natural key: every column except order_id. A double-submitted order
# gets a new order_id but is otherwise identical, so we ignore order_id.
NATURAL_KEY = [
    "customer_id", "product_id", "order_date", "quantity",
    "discount_pct", "payment_method", "rating", "returned",
]

# keep="first": the first occurrence is the genuine order and stays (False);
# every later copy is marked True as a duplicate.
is_duplicate = orders.duplicated(subset=NATURAL_KEY, keep="first")

# Keep the dropped rows aside: Task 5 needs their value for the reconciliation.
duplicates_dropped = orders[is_duplicate].copy()
orders_clean = orders[~is_duplicate].copy()

print("Duplicate rows flagged:", is_duplicate.sum())
print("Dropped order_ids:", ", ".join(duplicates_dropped["order_id"]))
print("orders_clean shape:", orders_clean.shape)

# ---------------------------------------------------------------------
# Task 4 - Impute missing values (on the de-duplicated data)
# ---------------------------------------------------------------------
section("Task 4 - Impute missing values")

missing_discount = orders_clean["discount_pct"].isnull().sum()
missing_rating = orders_clean["rating"].isnull().sum()
print("Rows with missing discount_pct:", missing_discount)
print("Rows with missing rating:      ", missing_rating)

# Business rule: a blank discount means no promo code was applied, i.e. 0%.
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)

# Median of the ratings we do have. Computed after removing duplicates,
# so the double-submitted rows cannot pull it in their direction.
rating_median = orders_clean["rating"].median()
print("Median rating (before imputing):", rating_median)
orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)

print("\nMissing values after imputing:")
print(orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

# ---------------------------------------------------------------------
# Task 5 - Merge and reconcile against Part 1
# ---------------------------------------------------------------------
section("Task 5 - Merge and reconcile against Part 1")


def add_order_value(df):
    """Attach product prices and compute order_value for each row.

    Same formula as SQL Report (a): quantity * price * (1 - discount/100),
    with a missing discount treated as 0%.
    """
    df = df.merge(products, on="product_id", how="left")
    discount = df["discount_pct"].fillna(0)
    df["order_value"] = df["quantity"] * df["price"] * (1 - discount / 100)
    return df


# Cleaned data: 175 rows, joined to products and customers.
merged = add_order_value(orders_clean).merge(customers, on="customer_id", how="left")
print("Merged shape:", merged.shape, "(still 175 rows, so no order was lost or duplicated by the join)")

cleaned_total = merged["order_value"].sum()
print(f"Cleaned total revenue (175 rows):         INR {cleaned_total:,.2f}")

# Raw data: all 180 rows, recomputed here the same way SQL Report (a) did.
raw_total = add_order_value(orders)["order_value"].sum()
print(f"Raw total revenue (180 rows, = Part 1 a): INR {raw_total:,.2f}")

difference = raw_total - cleaned_total
print(f"Difference (raw - cleaned):               INR {difference:,.2f}")

# Independent check: value of the 5 dropped duplicate rows, summed on their own.
dropped_value = add_order_value(duplicates_dropped)
print("\nValue of each dropped duplicate row:")
print(dropped_value[["order_id", "quantity", "price", "discount_pct", "order_value"]].to_string(index=False))
duplicates_total = dropped_value["order_value"].sum()
print(f"Sum of the 5 dropped duplicates:          INR {duplicates_total:,.2f}")

# Compare at paisa level (2 decimals) to ignore tiny floating-point noise.
reconciled = round(difference, 2) == round(duplicates_total, 2)
print("Difference fully explained by duplicates?", "YES" if reconciled else "NO - investigate")

print(f"""
Reconciliation note:
Part 1 Report (a) computed total revenue of INR {raw_total:,.2f} on the raw orders table
({len(orders)} rows). After cleaning, total revenue is INR {cleaned_total:,.2f} on {len(merged)} rows.
The gap of INR {difference:,.2f} is caused entirely by the {len(duplicates_dropped)} double-submitted orders
removed in Task 3 ({", ".join(duplicates_dropped["order_id"])}): their combined order_value,
summed independently above, is INR {duplicates_total:,.2f}, which equals the gap exactly.
The Task 4 imputation does not change revenue at all: SQL already treated a missing
discount as 0% using COALESCE, which is the same value we filled in, and rating is not
part of the revenue formula. The raw figure was overstated by double-counted sales.""")

# ---------------------------------------------------------------------
# Task 6 - IQR outlier detection on quantity
# ---------------------------------------------------------------------
section("Task 6 - IQR outlier detection on quantity")

q1 = merged["quantity"].quantile(0.25)
q3 = merged["quantity"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
print(f"Q1 = {q1}, Q3 = {q3}, IQR = {iqr}, lower = {lower}, upper = {upper}")

# Flag, do not drop: the rows stay in the data with is_outlier = True,
# so later tasks can show results both with and without them.
merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)

outliers = merged[merged["is_outlier"]]
print(f"\nOrders outside [{lower}, {upper}]: {len(outliers)}")
print(outliers[["order_id", "customer_id", "order_date", "quantity", "order_value"]].to_string(index=False))
print("Rows still in merged data:", len(merged), "(outliers flagged, not dropped)")

# ---------------------------------------------------------------------
# Task 7 - Hypothesis: does COD have a higher return rate?
# ---------------------------------------------------------------------
section("Task 7 - Hypothesis: COD orders have a higher return rate")

print("Hypothesis: Cash-on-Delivery (COD) orders are returned more often than")
print("prepaid orders (CARD, UPI), because the customer has not paid upfront")
print("and can refuse or return the parcel at no cost to themselves.\n")

# returned is 0/1, so the mean of returned = share of orders returned.
by_payment = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
by_payment["return_rate_pct"] = (by_payment["mean"] * 100).round(1)
by_payment = by_payment.sort_values("return_rate_pct", ascending=False)
print(by_payment)

cod_rate = by_payment.loc["COD", "return_rate_pct"]
other_rates = by_payment.drop(index="COD")["return_rate_pct"]
verdict = "Confirmed" if cod_rate > other_rates.max() else "Busted"

card_rate = by_payment.loc["CARD", "return_rate_pct"]
print(f"\nCOD return rate {cod_rate}% vs CARD {card_rate}% "
      f"(about {cod_rate / card_rate:.1f}x) and UPI {by_payment.loc['UPI', 'return_rate_pct']}%.")
print("Verdict:", verdict)

# ---------------------------------------------------------------------
# Task 8 - Multi-level segmentation: payment method x city tier
# ---------------------------------------------------------------------
section("Task 8 - Segmentation: payment method x city tier")

segments = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
segments["return_rate_pct"] = (segments["mean"] * 100).round(1)
segments = segments.sort_values("return_rate_pct", ascending=False)
print(segments)

# idxmax gives the (payment_method, city_tier) label of the highest rate.
risk_method, risk_tier = segments["return_rate_pct"].idxmax()
risk_rate = segments.loc[(risk_method, risk_tier), "return_rate_pct"]
risk_count = segments.loc[(risk_method, risk_tier), "count"]
print(f"\nHighest-risk segment: {risk_method} + Tier-{risk_tier} cities "
      f"at {risk_rate}% ({risk_count} orders)")

cod_t1 = segments.loc[("COD", 1)]
cod_t2 = segments.loc[("COD", 2)]
print(f"\nCOD is not uniform across tiers: {int(cod_t1['count'])} Tier-1 COD orders return at "
      f"{cod_t1['return_rate_pct']}%, while {int(cod_t2['count'])} Tier-2 COD orders return at "
      f"{cod_t2['return_rate_pct']}%.")
print(f"The blended COD rate of {cod_rate}% hides that the problem is concentrated in Tier-2 cities.")

# ---------------------------------------------------------------------
# Task 9 - Correlation analysis
# ---------------------------------------------------------------------
section("Task 9 - Correlation analysis")

CORR_COLUMNS = ["rating", "returned", "discount_pct", "quantity"]
corr_matrix = merged[CORR_COLUMNS].corr()
print("Correlation matrix (Pearson r):")
print(corr_matrix.round(3))


def strength_band(r):
    """Label a correlation using the taught bands, based on its size |r|."""
    size = abs(r)
    if size < 0.2:
        return "negligible"
    elif size < 0.4:
        return "weak"
    elif size < 0.7:
        return "moderate"
    return "strong"


print("\nStrength of each pair (bands: 0-0.19 negligible, 0.2-0.39 weak, "
      "0.4-0.69 moderate, 0.7-1.0 strong):")
# Walk the upper triangle of the matrix so each of the 6 pairs appears once.
for i, col_a in enumerate(CORR_COLUMNS):
    for col_b in CORR_COLUMNS[i + 1:]:
        r = corr_matrix.loc[col_a, col_b]
        print(f"  {col_a:>12} vs {col_b:<12} r = {r:+.3f}  -> {strength_band(r)}")

discount_return_r = corr_matrix.loc["discount_pct", "returned"]
discount_verdict = "Busted" if strength_band(discount_return_r) == "negligible" else "Supported"
print(f"\nHypothesis 'higher discounts reduce returns': r = {discount_return_r:+.2f} "
      f"({strength_band(discount_return_r)}) -> {discount_verdict}")
print("Discount level has no meaningful linear relationship with returns, so")
print("discounting is not a lever for reducing returns in this data.")

# ---------------------------------------------------------------------
# Task 10 - Outlier-corrected monthly revenue trend
# ---------------------------------------------------------------------
section("Task 10 - Monthly revenue, with and without outliers")

# Text like '2026-01-28' becomes a real date, so we can pull out the month.
merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)

monthly_with_outliers = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_corrected = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)

monthly = pd.DataFrame({
    "with_outliers": monthly_with_outliers,
    "outlier_corrected": monthly_corrected,
})
print("Monthly revenue (INR):")
print(monthly.to_string(float_format=lambda x: f"{x:,.2f}"))

apparent_peak = monthly_with_outliers.idxmax()
true_peak = monthly_corrected.idxmax()
print(f"\n(1) Including outliers, the highest month is {apparent_peak} "
      f"at INR {monthly_with_outliers[apparent_peak]:,.2f}.")
print(f"(2) Excluding outliers, the highest month is {true_peak} "
      f"at INR {monthly_corrected[true_peak]:,.2f}.")

# Re-select the outliers from merged: the Task 6 `outliers` table is a
# snapshot taken before order_date was converted, so its dates are still text.
outlier_rows = merged[merged["is_outlier"]]
outlier_list = ", ".join(
    f"{row.order_id} on {row.order_date:%Y-%m-%d}" for row in outlier_rows.itertuples()
)
# Month names ('2026-03' -> 'March') for the plain-English statements.
apparent_name = pd.Period(apparent_peak).strftime("%B")
true_name = pd.Period(true_peak).strftime("%B")

print(f"\n{apparent_name}'s apparent lead is an artifact: both bulk outlier orders "
      f"({outlier_list}) landed in {apparent_name}.")
print(f"Without them, {apparent_name} falls to INR {monthly_corrected[apparent_peak]:,.2f}, "
      f"and {true_name} ({true_peak}) is the genuine peak month at INR "
      f"{monthly_corrected[true_peak]:,.2f}.")

# ---------------------------------------------------------------------
# Export - narrator/findings.json (Part 3, Task 1)
# ---------------------------------------------------------------------
section("Export - writing narrator/findings.json")

# Every value below is a variable computed earlier in this script; nothing
# is typed in by hand, so the file can never drift from the analysis.
# float()/int() convert pandas number types into plain Python numbers,
# which the json module knows how to write.
findings = {
    "cleaned_total_revenue_inr": round(float(cleaned_total), 2),
    "raw_total_revenue_inr": round(float(raw_total), 2),
    "duplicate_reconciliation_delta_inr": round(float(difference), 2),
    "return_rate_by_payment": {
        method: float(rate) for method, rate in by_payment["return_rate_pct"].items()
    },
    "highest_risk_segment": {
        "payment_method": risk_method,
        "city_tier": int(risk_tier),
        "return_rate_pct": float(risk_rate),
    },
    "true_peak_month": {
        "month": true_peak,
        "revenue_inr": float(monthly_corrected[true_peak]),
    },
    "outlier_inflated_month": {
        "month": apparent_peak,
        "apparent_revenue_inr": float(monthly_with_outliers[apparent_peak]),
        "corrected_revenue_inr": float(monthly_corrected[apparent_peak]),
    },
    # Extra key (beyond the 7 required): the full corrected monthly series,
    # so analysis/visualize.py can draw the trend line without recomputing it.
    "monthly_revenue_corrected_inr": {
        month: float(value) for month, value in monthly_corrected.items()
    },
}

findings_path = REPO_ROOT / "narrator" / "findings.json"
with open(findings_path, "w", encoding="utf-8") as f:
    json.dump(findings, f, indent=2)
    f.write("\n")

print(f"Wrote {findings_path.relative_to(REPO_ROOT)}:")
print(json.dumps(findings, indent=2))
