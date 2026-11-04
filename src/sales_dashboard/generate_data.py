"""Build a realistic *synthetic* sales database (SQLite) for a UK retailer.

Two years of order lines (2024-2025) across 8 UK regions, 2 channels, 2 customer
segments and 40 products in 5 categories. The data has:
  * year-on-year growth (online grows faster than in-store),
  * seasonality (November/December peak, quieter January/February),
  * weekend uplift for in-store sales,
  * discounts that reduce margin.
All products and figures are fictional.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATABASE_PATH, END_DATE, RANDOM_SEED, START_DATE

REGIONS = {  # region: relative size
    "London": 1.6, "South East": 1.3, "North West": 1.0, "Midlands": 1.0,
    "Scotland": 0.8, "South West": 0.7, "Wales": 0.5, "Northern Ireland": 0.45,
}
CATEGORIES = {  # category: (price range, cost ratio, products)
    "Electronics": ((60, 450), 0.74, ["Wireless Earbuds", "Bluetooth Speaker", "Smartwatch", "Tablet 10in",
                                      "Noise-Cancelling Headphones", "Portable Charger", "E-Reader", "Action Camera"]),
    "Home & Kitchen": ((15, 180), 0.58, ["Air Fryer", "Coffee Grinder", "Cast Iron Pan", "Knife Set", "Kettle",
                                         "Blender", "Storage Jars Set", "Toaster"]),
    "Clothing": ((12, 120), 0.45, ["Rain Jacket", "Running Shoes", "Wool Jumper", "Denim Jeans", "Hoodie",
                                   "Trainers", "Winter Coat", "T-Shirt Pack"]),
    "Sports & Outdoors": ((10, 220), 0.55, ["Yoga Mat", "Dumbbell Set", "Hiking Backpack", "Water Bottle",
                                            "Camping Tent", "Bike Lights", "Resistance Bands", "Foam Roller"]),
    "Beauty": ((6, 70), 0.40, ["Skincare Set", "Hair Dryer", "Electric Toothbrush", "Perfume 50ml",
                               "Shaving Kit", "Moisturiser", "Hair Straightener", "Bath Gift Set"]),
}
MONTH_SEASONALITY = {1: 0.75, 2: 0.78, 3: 0.92, 4: 0.95, 5: 1.0, 6: 1.0, 7: 1.02, 8: 1.0, 9: 0.95,
                     10: 1.05, 11: 1.35, 12: 1.55}

SCHEMA = """
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS products;
CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    list_price   REAL NOT NULL CHECK (list_price > 0),
    unit_cost    REAL NOT NULL CHECK (unit_cost > 0)
);
CREATE TABLE sales (
    line_id     INTEGER PRIMARY KEY,
    order_id    TEXT NOT NULL,
    order_date  TEXT NOT NULL,              -- ISO date YYYY-MM-DD
    region      TEXT NOT NULL,
    channel     TEXT NOT NULL CHECK (channel IN ('Online', 'In-store')),
    segment     TEXT NOT NULL CHECK (segment IN ('Consumer', 'Business')),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  REAL NOT NULL,
    discount    REAL NOT NULL CHECK (discount >= 0 AND discount < 1),
    revenue     REAL NOT NULL,              -- quantity * unit_price * (1 - discount)
    cost        REAL NOT NULL,              -- quantity * unit_cost
    profit      REAL NOT NULL               -- revenue - cost
);
CREATE INDEX ix_sales_date ON sales(order_date);
CREATE INDEX ix_sales_region ON sales(region);
CREATE INDEX ix_sales_product ON sales(product_id);
"""


def build_products(rng: np.random.Generator) -> pd.DataFrame:
    rows, pid = [], 1
    for cat, ((lo, hi), cost_ratio, names) in CATEGORIES.items():
        for name in names:
            price = round(round(float(rng.uniform(lo, hi))) - 0.01, 2)  # retail "x.99" pricing
            cost = round(price * cost_ratio * rng.uniform(0.9, 1.1), 2)
            rows.append((pid, name, cat, price, cost))
            pid += 1
    return pd.DataFrame(rows, columns=["product_id", "product_name", "category", "list_price", "unit_cost"])


def build_sales(products: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    days = pd.date_range(START_DATE, END_DATE, freq="D")
    regions, weights = list(REGIONS), np.array(list(REGIONS.values()))
    region_p = weights / weights.sum()
    popularity = rng.gamma(1.5, 1.0, len(products))
    cheapness = 1 / np.sqrt(products["list_price"].to_numpy())
    product_p = popularity * cheapness
    product_p /= product_p.sum()

    frames = []
    for day in days:
        t = (day - days[0]).days / 365.0
        season = MONTH_SEASONALITY[day.month]
        for channel, base, growth in (("Online", 26, 0.22), ("In-store", 30, 0.04)):
            weekend = 1.25 if (channel == "In-store" and day.day_of_week >= 5) else 1.0
            n = rng.poisson(base * season * weekend * (1 + growth) ** t)
            if n == 0:
                continue
            idx = rng.choice(len(products), n, p=product_p)
            discount = np.where(rng.random(n) < (0.35 if day.month in (11, 1) else 0.15),
                                rng.choice([0.1, 0.15, 0.2, 0.25], n), 0.0)
            frames.append(pd.DataFrame({
                "order_date": day.strftime("%Y-%m-%d"),
                "region": rng.choice(regions, n, p=region_p),
                "channel": channel,
                "segment": np.where(rng.random(n) < 0.18, "Business", "Consumer"),
                "product_id": products["product_id"].to_numpy()[idx],
                "quantity": np.where(rng.random(n) < 0.18, rng.integers(2, 6, n), 1),
                "discount": discount,
            }))
    sales = pd.concat(frames, ignore_index=True)
    sales = sales.merge(products[["product_id", "list_price", "unit_cost"]], on="product_id", how="left")
    sales["quantity"] = np.where(sales["segment"] == "Business", sales["quantity"] * 3, sales["quantity"])
    sales["unit_price"] = sales["list_price"]
    sales["revenue"] = (sales["quantity"] * sales["unit_price"] * (1 - sales["discount"])).round(2)
    sales["cost"] = (sales["quantity"] * sales["unit_cost"]).round(2)
    sales["profit"] = (sales["revenue"] - sales["cost"]).round(2)
    sales = sales.sort_values(["order_date", "channel"]).reset_index(drop=True)
    sales.insert(0, "line_id", np.arange(1, len(sales) + 1))
    sales.insert(1, "order_id", [f"SO{1_000_000 + i}" for i in range(len(sales))])
    return sales.drop(columns=["list_price", "unit_cost"])


def build_database(path: Path = DATABASE_PATH, seed: int = RANDOM_SEED) -> dict:
    rng = np.random.default_rng(seed)
    products = build_products(rng)
    sales = build_sales(products, rng)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA)
        products.to_sql("products", con, if_exists="append", index=False)
        sales.to_sql("sales", con, if_exists="append", index=False)
    return {"products": len(products), "sales_lines": len(sales), "path": str(path)}


def ensure_database(path: Path = DATABASE_PATH) -> None:
    """Create the database on first run so the app works straight after cloning."""
    if not path.exists():
        build_database(path)
