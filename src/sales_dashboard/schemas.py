"""Pydantic response models: they document the API (see /docs) and validate what we send."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class FilterOptions(BaseModel):
    regions: list[str]
    channels: list[str]
    categories: list[str]
    min_date: str
    max_date: str


class Period(BaseModel):
    start: str
    end: str


class KPIs(BaseModel):
    revenue: float
    profit: float
    orders: int
    units: int
    margin_pct: float
    avg_order_value: float
    change_pct: dict[str, Optional[float]]
    previous_period: Period


class TrendPoint(BaseModel):
    period: str
    revenue: float
    profit: float
    orders: int


class RegionRow(BaseModel):
    region: str
    revenue: float
    profit: float
    orders: int
    margin_pct: float
    share_pct: float


class CategoryRow(BaseModel):
    category: str
    revenue: float
    profit: float
    units: int
    margin_pct: float
    share_pct: float


class ChannelRow(BaseModel):
    channel: str
    revenue: float
    profit: float
    orders: int


class ProductRow(BaseModel):
    product_id: int
    product_name: str
    category: str
    units: int
    revenue: float
    profit: float
    margin_pct: float


class Health(BaseModel):
    status: str
    sales_lines: int
