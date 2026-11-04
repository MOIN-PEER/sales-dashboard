"""FastAPI application: JSON endpoints under /api and the Vue frontend at /.

Run from the project root:
    uvicorn sales_dashboard.api:app --reload
then open http://127.0.0.1:8000 (dashboard) or http://127.0.0.1:8000/docs (interactive API docs).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, queries
from .config import DATABASE_PATH, FRONTEND_DIR
from .generate_data import ensure_database
from .schemas import (CategoryRow, ChannelRow, FilterOptions, Health, KPIs, ProductRow, RegionRow,
                      TrendPoint)

ensure_database(DATABASE_PATH)
con = queries.connect(DATABASE_PATH)
OPTIONS = queries.filter_options(con)

app = FastAPI(
    title="Sales Performance Dashboard API",
    version=__version__,
    description="KPIs, revenue trends, regional and product breakdowns for a (synthetic) UK retailer.",
)
# Allows the frontend to be served from another port during development (e.g. VS Code Live Server).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def get_filters(
    start: Optional[date] = Query(None, description="First day, YYYY-MM-DD (default: first day in data)"),
    end: Optional[date] = Query(None, description="Last day, YYYY-MM-DD (default: last day in data)"),
    region: Optional[str] = Query(None, description="Region name, e.g. London"),
    channel: Optional[str] = Query(None, description="Online or In-store"),
    category: Optional[str] = Query(None, description="Product category"),
) -> queries.Filters:
    """Shared by every endpoint, so all charts always use identical, validated filters."""
    start = start or date.fromisoformat(OPTIONS["min_date"])
    end = end or date.fromisoformat(OPTIONS["max_date"])
    if start > end:
        raise HTTPException(400, "start must be on or before end")
    for value, allowed, name in ((region, OPTIONS["regions"], "region"), (channel, OPTIONS["channels"], "channel"),
                                 (category, OPTIONS["categories"], "category")):
        if value is not None and value not in allowed:
            raise HTTPException(400, f"Unknown {name} '{value}'. Allowed: {', '.join(allowed)}")
    return queries.Filters(start, end, region or None, channel or None, category or None)


@app.get("/api/health", response_model=Health, tags=["meta"])
def health():
    return {"status": "ok", "sales_lines": con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]}


@app.get("/api/filters", response_model=FilterOptions, tags=["meta"])
def filters():
    return OPTIONS


@app.get("/api/kpis", response_model=KPIs, tags=["dashboard"])
def kpis(f: queries.Filters = Depends(get_filters)):
    return queries.kpis(con, f)


@app.get("/api/revenue-trend", response_model=list[TrendPoint], tags=["dashboard"])
def revenue_trend(f: queries.Filters = Depends(get_filters),
                  grain: Literal["day", "week", "month", "quarter"] = "month"):
    return queries.revenue_trend(con, f, grain)


@app.get("/api/regions", response_model=list[RegionRow], tags=["dashboard"])
def regions(f: queries.Filters = Depends(get_filters)):
    return queries.by_region(con, f)


@app.get("/api/categories", response_model=list[CategoryRow], tags=["dashboard"])
def categories(f: queries.Filters = Depends(get_filters)):
    return queries.by_category(con, f)


@app.get("/api/channels", response_model=list[ChannelRow], tags=["dashboard"])
def channels(f: queries.Filters = Depends(get_filters)):
    return queries.by_channel(con, f)


@app.get("/api/top-products", response_model=list[ProductRow], tags=["dashboard"])
def top_products(f: queries.Filters = Depends(get_filters), limit: int = Query(10, ge=1, le=40),
                 sort: Literal["revenue", "profit", "units"] = "revenue"):
    return queries.top_products(con, f, limit, sort)


@app.get("/api/export/products.csv", tags=["export"])
def export_products(f: queries.Filters = Depends(get_filters)):
    """Download every product's figures for the current filters as CSV."""
    rows = queries.top_products(con, f, limit=1000)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(ProductRow.model_fields))
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=products.csv"})


# Mounted last so /api routes take priority; html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
