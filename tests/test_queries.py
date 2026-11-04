"""Reconciliation tests: every breakdown must add back up to the KPI total for the same filters."""

from datetime import date

import pytest

from sales_dashboard import queries as q

Y2025 = q.Filters(date(2025, 1, 1), date(2025, 12, 31))
FILTER_CASES = [
    Y2025,
    q.Filters(date(2024, 1, 1), date(2025, 12, 31), region="Scotland"),
    q.Filters(date(2025, 10, 1), date(2025, 12, 31), channel="Online", category="Electronics"),
]


@pytest.mark.parametrize("f", FILTER_CASES)
def test_breakdowns_reconcile_to_kpi_revenue(con, f):
    total = q.kpis(con, f)["revenue"]
    for rows in (q.by_region(con, f), q.by_category(con, f), q.by_channel(con, f), q.revenue_trend(con, f)):
        assert sum(r["revenue"] for r in rows) == pytest.approx(total, abs=1.0)


def test_kpis_match_independent_sql(raw):
    expected = raw.execute("""SELECT ROUND(SUM(revenue), 2) FROM sales
                              WHERE order_date BETWEEN '2025-01-01' AND '2025-12-31'""").fetchone()[0]
    from sales_dashboard.queries import connect
    assert q.kpis(connect(q.DATABASE_PATH), Y2025)["revenue"] == pytest.approx(expected)


def test_previous_period_whole_year_and_custom_range():
    assert Y2025.previous_period().start == date(2024, 1, 1)
    assert Y2025.previous_period().end == date(2024, 12, 31)
    q4 = q.Filters(date(2025, 10, 1), date(2025, 12, 31)).previous_period()
    assert (q4.start, q4.end) == (date(2025, 7, 1), date(2025, 9, 30))
    custom = q.Filters(date(2025, 3, 10), date(2025, 3, 19)).previous_period()
    assert (custom.start, custom.end) == (date(2025, 2, 28), date(2025, 3, 9))


def test_no_previous_data_gives_null_change(con):
    k = q.kpis(con, q.Filters(date(2024, 1, 1), date(2024, 12, 31)))
    assert k["change_pct"]["revenue"] is None


def test_shares_sum_to_100(con):
    assert sum(r["share_pct"] for r in q.by_region(con, Y2025)) == pytest.approx(100, abs=0.5)


def test_top_products_sorted_and_limited(con):
    rows = q.top_products(con, Y2025, limit=5, sort="profit")
    assert len(rows) == 5
    assert [r["profit"] for r in rows] == sorted((r["profit"] for r in rows), reverse=True)


def test_empty_selection_returns_zeros_not_errors(con):
    k = q.kpis(con, q.Filters(date(2030, 1, 1), date(2030, 1, 31)))
    assert k["revenue"] == 0 and k["orders"] == 0 and k["margin_pct"] == 0


def test_filter_values_are_parameters_not_sql(con):
    evil = q.Filters(date(2025, 1, 1), date(2025, 12, 31), region="London' OR '1'='1")
    assert q.kpis(con, evil)["revenue"] == 0
