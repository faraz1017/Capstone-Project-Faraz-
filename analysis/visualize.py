"""
analysis/visualize.py — Part 2, Task 11: the two required charts.

Reads the verified numbers from narrator/findings.json (written by
analysis/clean_and_eda.py), so the charts can never show a figure the
analysis did not compute.

Run from the repo root, after clean_and_eda.py:
    python analysis/visualize.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to files; no pop-up window needed
import matplotlib.pyplot as plt  # noqa: E402  (must come after matplotlib.use)
import pandas as pd  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_PATH = REPO_ROOT / "narrator" / "findings.json"
OUTPUT_DIR = REPO_ROOT / "visualizations"

# Colours: one blue for the data, grey for everything that is context.
HIGHLIGHT = "#2a78d6"
MUTED = "#b4b2ab"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e6e5e0"

# Fixed font and no "Software" stamp, so the PNG bytes are identical every run.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
})
SAVE_OPTIONS = {"dpi": 150, "bbox_inches": "tight", "metadata": {"Software": None}}

if not FINDINGS_PATH.exists():
    sys.exit("narrator/findings.json not found - run `python analysis/clean_and_eda.py` first.")

with open(FINDINGS_PATH, encoding="utf-8") as f:
    findings = json.load(f)

OUTPUT_DIR.mkdir(exist_ok=True)


def style_axes(ax):
    """Quiet axes: no top/right border, light horizontal grid behind the data."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------------
# Chart 1 - Return rate by payment method (bar chart, descending)
# ---------------------------------------------------------------------
rates = pd.Series(findings["return_rate_by_payment"]).sort_values(ascending=False)
top_method = rates.index[0]
times_card = rates[top_method] / rates["CARD"]

fig, ax = plt.subplots(figsize=(7, 4.5))
colors = [HIGHLIGHT if method == top_method else MUTED for method in rates.index]
bars = ax.bar(rates.index, rates.values, color=colors, width=0.55)

# Exact percentage on top of each bar.
for bar, rate in zip(bars, rates.values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{rate:.1f}%", ha="center", va="bottom", color=TEXT, fontsize=12, fontweight="bold")

ax.set_title(f"{top_method} Returns at {rates[top_method]:.1f}% — {times_card:.0f}x Card",
             loc="left", fontsize=14, fontweight="bold", color=TEXT)
ax.set_xlabel("Payment method (cleaned)")
ax.set_ylabel("Return rate (%)")
ax.set_ylim(0, rates.max() * 1.18)
style_axes(ax)

chart1_path = OUTPUT_DIR / "return_rate_by_payment.png"
fig.savefig(chart1_path, **SAVE_OPTIONS)
plt.close(fig)
print("Saved", chart1_path.relative_to(REPO_ROOT))
print(rates.to_string())

# ---------------------------------------------------------------------
# Chart 2 - Outlier-corrected monthly revenue (line chart)
# ---------------------------------------------------------------------
monthly = pd.Series(findings["monthly_revenue_corrected_inr"])
peak_month = findings["true_peak_month"]["month"]
peak_value = findings["true_peak_month"]["revenue_inr"]

# '2026-03' -> 'Mar 2026' for readable tick labels.
labels = [pd.Period(m).strftime("%b %Y") for m in monthly.index]
peak_label = pd.Period(peak_month).strftime("%B %Y")
peak_position = list(monthly.index).index(peak_month)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(labels, monthly.values, color=HIGHLIGHT, linewidth=2, marker="o", markersize=7)

# Label only the peak, so the eye goes straight to it.
ax.annotate(f"Peak: INR {peak_value:,.2f}", xy=(peak_position, peak_value),
            xytext=(0, 12), textcoords="offset points", ha="center",
            color=TEXT, fontsize=11, fontweight="bold")

ax.set_title(f"Monthly Revenue Peaks in {peak_label}",
             loc="left", fontsize=14, fontweight="bold", color=TEXT, pad=28)
# Smaller subtitle under the title, explaining what "corrected" means.
ax.text(0, 1.04, "Outlier-corrected: bulk orders flagged by the IQR rule are excluded",
        transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY)
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (INR)")
ax.set_ylim(0, monthly.max() * 1.18)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
style_axes(ax)

chart2_path = OUTPUT_DIR / "monthly_revenue_trend.png"
fig.savefig(chart2_path, **SAVE_OPTIONS)
plt.close(fig)
print("\nSaved", chart2_path.relative_to(REPO_ROOT))
print(monthly.to_string())
