"""All SQL used by the dashboard, in one place.

Every query takes the same Filters object, so every chart on the page always
describes exactly the same slice of data. Values from the user are only ever
passed as SQL parameters (never formatted into the SQL string).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from .config import DATABASE_PATH


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    region: Optional[str] = None
    channel: Optional[str] = None
    category: Optional[str] = None

    def where(self, alias_sales: str = "s", alias_products: str = "p") -> tuple[str, list]:
        clauses = [f"{alias_sales}.order_date BETWEEN ? AND ?"]
        params: list = [self.start.isoformat(), self.end.isoformat()]
        if self.region:
            clauses.append(f"{alias_sales}.region = ?")
            params.append(self.region)
        if self.channel:
            clauses.append(f"{alias_sales}.channel = ?")
            params.append(self.channel)
        if self.category:
            clauses.append(f"{alias_products}.category = ?")
            params.append(self.category)
        return " AND ".join(clauses), params

    def previous_period(self) -> "Filters":
        """The comparable period immediately before this one (for % change on KPI cards).

        Whole calendar months are compared with the same number of whole months before
        (so 2025 is compared with 2024, and Q4 with Q3); any other range is compared
        with the same number of days immediately before it.
        """
        prev_end = self.start - timedelta(days=1)
        if self.start.day == 1 and (self.end + timedelta(days=1)).day == 1:
            months = (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1
            m = self.start.year * 12 + (self.start.month - 1) - months
            prev_start = date(m // 12, m % 12 + 1, 1)
        else:
            prev_start = prev_end - timedelta(days=(self.end - self.start).days)
        return Filters(prev_start, prev_end, self.region, self.channel, self.category)


FROM = "FROM sales s JOIN products p ON p.product_id = s.product_id"


def connect(path=DATABASE_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _rows(con: sqlite3.Connection, sql: str, params: list) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def filter_options(con: sqlite3.Connection) -> dict:
    one = lambda sql: [r[0] for r in con.execute(sql)]  # noqa: E731
    lo, hi = con.execute("SELECT MIN(order_date), MAX(order_date) FROM sales").fetchone()
    return {
        "regions": one("SELECT DISTINCT region FROM sales ORDER BY region"),
        "channels": one("SELECT DISTINCT channel FROM sales ORDER BY channel"),
        "categories": one("SELECT DISTINCT category FROM products ORDER BY category"),
        "min_date": lo,
        "max_date": hi,
    }


def _totals(con: sqlite3.Connection, f: Filters) -> dict:
    where, params = f.where()
    row = con.execute(f"""
        SELECT ROUND(COALESCE(SUM(s.revenue), 0), 2) AS revenue,
               ROUND(COALESCE(SUM(s.profit), 0), 2)  AS profit,
               COUNT(DISTINCT s.order_id)            AS orders,
               COALESCE(SUM(s.quantity), 0)          AS units
        {FROM} WHERE {where}""", params).fetchone()
    d = dict(row)
    d["margin_pct"] = round(100 * d["profit"] / d["revenue"], 1) if d["revenue"] else 0.0
    d["avg_order_value"] = round(d["revenue"] / d["orders"], 2) if d["orders"] else 0.0
    return d


def _change(now: float, before: float) -> Optional[float]:
    return round(100 * (now - before) / before, 1) if before else None


def kpis(con: sqlite3.Connection, f: Filters) -> dict:
    cur, prev = _totals(con, f), _totals(con, f.previous_period())
    out = dict(cur)
    out["change_pct"] = {k: _change(cur[k], prev[k]) for k in ("revenue", "profit", "orders", "avg_order_value")}
    out["change_pct"]["margin_pts"] = round(cur["margin_pct"] - prev["margin_pct"], 1) if prev["revenue"] else None
    out["previous_period"] = {"start": f.previous_period().start.isoformat(),
                              "end": f.previous_period().end.isoformat()}
    return out


GRAIN_SQL = {"day": "s.order_date", "week": "strftime('%Y-W%W', s.order_date)",
             "month": "substr(s.order_date, 1, 7)", "quarter":
             "substr(s.order_date, 1, 4) || '-Q' || ((CAST(substr(s.order_date, 6, 2) AS INTEGER) + 2) / 3)"}


def revenue_trend(con: sqlite3.Connection, f: Filters, grain: str = "month") -> list[dict]:
    period = GRAIN_SQL[grain]
    where, params = f.where()
    return _rows(con, f"""
        SELECT {period} AS period,
               ROUND(SUM(s.revenue), 2) AS revenue,
               ROUND(SUM(s.profit), 2)  AS profit,
               COUNT(DISTINCT s.order_id) AS orders
        {FROM} WHERE {where}
        GROUP BY period ORDER BY period""", params)


def by_region(con: sqlite3.Connection, f: Filters) -> list[dict]:
    where, params = f.where()
    rows = _rows(con, f"""
        SELECT s.region,
               ROUND(SUM(s.revenue), 2) AS revenue,
               ROUND(SUM(s.profit), 2)  AS profit,
               COUNT(DISTINCT s.order_id) AS orders
        {FROM} WHERE {where}
        GROUP BY s.region ORDER BY revenue DESC""", params)
    total = sum(r["revenue"] for r in rows) or 1
    for r in rows:
        r["margin_pct"] = round(100 * r["profit"] / r["revenue"], 1) if r["revenue"] else 0.0
        r["share_pct"] = round(100 * r["revenue"] / total, 1)
    return rows


def by_category(con: sqlite3.Connection, f: Filters) -> list[dict]:
    where, params = f.where()
    rows = _rows(con, f"""
        SELECT p.category,
               ROUND(SUM(s.revenue), 2) AS revenue,
               ROUND(SUM(s.profit), 2)  AS profit,
               SUM(s.quantity)          AS units
        {FROM} WHERE {where}
        GROUP BY p.category ORDER BY revenue DESC""", params)
    total = sum(r["revenue"] for r in rows) or 1
    for r in rows:
        r["margin_pct"] = round(100 * r["profit"] / r["revenue"], 1) if r["revenue"] else 0.0
        r["share_pct"] = round(100 * r["revenue"] / total, 1)
    return rows


def by_channel(con: sqlite3.Connection, f: Filters) -> list[dict]:
    where, params = f.where()
    return _rows(con, f"""
        SELECT s.channel,
               ROUND(SUM(s.revenue), 2) AS revenue,
               ROUND(SUM(s.profit), 2)  AS profit,
               COUNT(DISTINCT s.order_id) AS orders
        {FROM} WHERE {where}
        GROUP BY s.channel ORDER BY revenue DESC""", params)


def top_products(con: sqlite3.Connection, f: Filters, limit: int = 10, sort: str = "revenue") -> list[dict]:
    order_col = {"revenue": "revenue", "profit": "profit", "units": "units"}[sort]  # whitelist, not user SQL
    where, params = f.where()
    rows = _rows(con, f"""
        SELECT p.product_id, p.product_name, p.category,
               SUM(s.quantity)          AS units,
               ROUND(SUM(s.revenue), 2) AS revenue,
               ROUND(SUM(s.profit), 2)  AS profit
        {FROM} WHERE {where}
        GROUP BY p.product_id ORDER BY {order_col} DESC LIMIT ?""", params + [limit])
    for r in rows:
        r["margin_pct"] = round(100 * r["profit"] / r["revenue"], 1) if r["revenue"] else 0.0
    return rows
