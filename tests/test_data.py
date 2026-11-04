"""The generated data must be internally consistent before any dashboard number can be trusted."""


def test_row_counts(raw):
    assert raw.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 40
    assert raw.execute("SELECT COUNT(*) FROM sales").fetchone()[0] > 40_000


def test_revenue_formula_holds_for_every_line(raw):
    bad = raw.execute("""SELECT COUNT(*) FROM sales
                         WHERE ABS(revenue - ROUND(quantity * unit_price * (1 - discount), 2)) > 0.011
                            OR ABS(profit - ROUND(revenue - cost, 2)) > 0.011""").fetchone()[0]
    assert bad == 0


def test_no_orphan_products(raw):
    assert raw.execute("""SELECT COUNT(*) FROM sales s LEFT JOIN products p USING (product_id)
                          WHERE p.product_id IS NULL""").fetchone()[0] == 0


def test_dates_cover_two_full_years(raw):
    lo, hi = raw.execute("SELECT MIN(order_date), MAX(order_date) FROM sales").fetchone()
    assert lo == "2024-01-01" and hi == "2025-12-31"


def test_generator_is_reproducible(tmp_path):
    from sales_dashboard.generate_data import build_database
    a = build_database(tmp_path / "a.db")
    b = build_database(tmp_path / "b.db")
    assert a["sales_lines"] == b["sales_lines"]


def test_seasonality_december_beats_january(raw):
    jan, dec = (raw.execute("SELECT SUM(revenue) FROM sales WHERE substr(order_date, 6, 2) = ?", (m,)).fetchone()[0]
                for m in ("01", "12"))
    assert dec > 1.5 * jan
