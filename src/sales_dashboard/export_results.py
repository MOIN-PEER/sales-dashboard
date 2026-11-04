"""Write the dashboard's numbers to outputs/ so results can be reviewed without running the app.

Produces:
  outputs/results/kpi_summary.json        headline KPIs for 2025 vs 2024 and all time
  outputs/results/monthly_trend.csv       revenue, profit and orders per month
  outputs/results/region_summary.csv      2025 by region, with growth vs 2024
  outputs/results/category_summary.csv    2025 by category
  outputs/results/channel_summary.csv     2025 vs 2024 by channel
  outputs/results/top_products_2025.csv   top 10 products of 2025
  outputs/results/insights.md             plain-English findings generated from the numbers
  outputs/figures/*.png                   static charts (used in the report)
"""

from __future__ import annotations

import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import queries as q  # noqa: E402
from .config import DATABASE_PATH, FIGURES_DIR, RESULTS_DIR  # noqa: E402
from .generate_data import ensure_database  # noqa: E402

BLUE, ORANGE, SOFT = "#2f6db5", "#f0a830", "#9dbbe0"
Y2024 = q.Filters(date(2024, 1, 1), date(2024, 12, 31))
Y2025 = q.Filters(date(2025, 1, 1), date(2025, 12, 31))
ALL = q.Filters(date(2024, 1, 1), date(2025, 12, 31))


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)


def _gbp(x, _=None):
    return f"£{x / 1e6:.1f}m" if abs(x) >= 1e6 else f"£{x / 1e3:.0f}k"


def export() -> dict:
    ensure_database(DATABASE_PATH)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    con = q.connect(DATABASE_PATH)

    k25, k24, kall = q.kpis(con, Y2025), q._totals(con, Y2024), q._totals(con, ALL)
    trend = pd.DataFrame(q.revenue_trend(con, ALL, "month"))
    reg25, reg24 = pd.DataFrame(q.by_region(con, Y2025)), pd.DataFrame(q.by_region(con, Y2024))
    reg = reg25.merge(reg24[["region", "revenue"]].rename(columns={"revenue": "revenue_2024"}), on="region")
    reg["growth_pct"] = (100 * (reg["revenue"] / reg["revenue_2024"] - 1)).round(1)
    cat = pd.DataFrame(q.by_category(con, Y2025))
    cat["profit_share_pct"] = (100 * cat["profit"] / cat["profit"].sum()).round(1)
    ch = pd.DataFrame(q.by_channel(con, Y2025)).merge(
        pd.DataFrame(q.by_channel(con, Y2024))[["channel", "revenue"]].rename(columns={"revenue": "revenue_2024"}),
        on="channel")
    ch["growth_pct"] = (100 * (ch["revenue"] / ch["revenue_2024"] - 1)).round(1)
    top = pd.DataFrame(q.top_products(con, Y2025, 10))

    summary = {"year_2025": k25, "year_2024": k24, "all_time": kall}
    (RESULTS_DIR / "kpi_summary.json").write_text(json.dumps(summary, indent=2))
    trend.to_csv(RESULTS_DIR / "monthly_trend.csv", index=False)
    reg.to_csv(RESULTS_DIR / "region_summary.csv", index=False)
    cat.to_csv(RESULTS_DIR / "category_summary.csv", index=False)
    ch.to_csv(RESULTS_DIR / "channel_summary.csv", index=False)
    top.to_csv(RESULTS_DIR / "top_products_2025.csv", index=False)

    # --- figures -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(trend["period"], trend["revenue"], color=BLUE, marker="o", ms=3, label="Revenue")
    ax.plot(trend["period"], trend["profit"], color=ORANGE, marker="o", ms=3, label="Profit")
    ax.fill_between(trend["period"], trend["revenue"], color=BLUE, alpha=0.08)
    ax.yaxis.set_major_formatter(_gbp)
    ax.set_xticks(trend["period"][::2])
    ax.tick_params(axis="x", rotation=45)
    ax.legend(frameon=False)
    _style(ax, "Monthly revenue and profit, 2024-2025")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_monthly_trend.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    r = reg.sort_values("revenue")
    ax.barh(r["region"], r["revenue"], color=BLUE)
    for y, (v, g) in enumerate(zip(r["revenue"], r["growth_pct"])):
        ax.text(v, y, f"  {_gbp(v)}  ({g:+.1f}%)", va="center", fontsize=9)
    ax.xaxis.set_major_formatter(_gbp)
    ax.set_xlim(0, r["revenue"].max() * 1.3)
    _style(ax, "2025 revenue by region (growth vs 2024)")
    ax.grid(axis="x", alpha=0.3)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "02_region_revenue.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = range(len(cat))
    ax.bar([i - 0.2 for i in x], cat["share_pct"], 0.4, color=BLUE, label="Share of revenue %")
    ax.bar([i + 0.2 for i in x], cat["profit_share_pct"], 0.4, color=ORANGE, label="Share of profit %")
    for i, m in zip(x, cat["margin_pct"]):
        ax.text(i, max(cat.loc[i, "share_pct"], cat.loc[i, "profit_share_pct"]) + 0.8, f"margin {m:.0f}%",
                ha="center", fontsize=9)
    ax.set_xticks(list(x), cat["category"])
    ax.set_ylim(0, max(cat["share_pct"].max(), cat["profit_share_pct"].max()) * 1.2)
    ax.legend(frameon=False, loc="upper right")
    _style(ax, "2025: share of revenue vs share of profit by category")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "03_category_revenue_vs_profit.png", dpi=160)
    plt.close(fig)

    ch_trend = pd.DataFrame(con.execute("""
        SELECT substr(order_date, 1, 7) AS period, channel, ROUND(SUM(revenue), 2) AS revenue
        FROM sales GROUP BY period, channel ORDER BY period""").fetchall(), columns=["period", "channel", "revenue"])
    piv = ch_trend.pivot(index="period", columns="channel", values="revenue")
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.plot(piv.index, piv["Online"], color=BLUE, marker="o", ms=3, label="Online")
    ax.plot(piv.index, piv["In-store"], color=ORANGE, marker="o", ms=3, label="In-store")
    ax.yaxis.set_major_formatter(_gbp)
    ax.set_xticks(piv.index[::2])
    ax.tick_params(axis="x", rotation=45)
    ax.legend(frameon=False)
    _style(ax, "Monthly revenue by channel: online overtakes in-store")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "04_channel_trend.png", dpi=160)
    plt.close(fig)

    # --- insights ------------------------------------------------------------------------
    c = k25["change_pct"]
    peak = trend.loc[trend["revenue"].idxmax()]
    low = cat.loc[cat["margin_pct"].idxmin()]
    best_growth = reg.loc[reg["growth_pct"].idxmax()]
    online = ch.set_index("channel").loc["Online"]
    instore = ch.set_index("channel").loc["In-store"]
    q4 = trend[trend["period"].str[5:7].isin(["10", "11", "12"]) & trend["period"].str.startswith("2025")]["revenue"].sum()
    lines = [
        "# Key insights (generated from the data by export_results.py)",
        "",
        f"1. **Growth.** 2025 revenue was {_gbp(k25['revenue'])}, up {c['revenue']}% on 2024; profit rose "
        f"{c['profit']}% and margin moved {c['margin_pts']:+} points to {k25['margin_pct']}%.",
        f"2. **Basket size fell.** Orders grew {c['orders']}% but average order value changed {c['avg_order_value']}%, "
        f"so growth came from more orders, not bigger ones.",
        f"3. **Seasonality.** The peak month was {peak['period']} ({_gbp(peak['revenue'])}). Q4 2025 delivered "
        f"{100 * q4 / k25['revenue']:.0f}% of the year's revenue, so stock and staffing should be planned around it.",
        f"4. **Online is the growth engine.** Online revenue grew {online['growth_pct']}% against "
        f"{instore['growth_pct']}% in-store, and is now {100 * online['revenue'] / k25['revenue']:.0f}% of revenue.",
        f"5. **Low-margin category.** {low['category']} brings {low['share_pct']}% of revenue but only "
        f"{low['profit_share_pct']}% of profit (margin {low['margin_pct']}%). Discounting it costs the most profit.",
        f"6. **Regions.** London is the largest region ({reg.iloc[0]['share_pct']}% of revenue); "
        f"{best_growth['region']} grew fastest ({best_growth['growth_pct']:+}%).",
        "",
        "_All data is synthetic, generated by src/sales_dashboard/generate_data.py._",
    ]
    (RESULTS_DIR / "insights.md").write_text("\n".join(lines) + "\n")
    return summary
