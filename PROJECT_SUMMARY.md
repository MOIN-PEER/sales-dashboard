# Project summary: Sales Performance Dashboard

**Author:** Mohamed Moin Peer  |  **Type:** Full-stack analytics project  |  **Stack:** Python, FastAPI, SQLite, Vue 3, Chart.js, pytest

## Problem
Managers need one place to see how sales are performing, compare with the previous period and drill into regions,
categories and products, without asking an analyst to run a new query each time.

## What I built
* A **synthetic SQLite database** of 48,994 order lines (2024-2025, 8 UK regions, 2 channels, 40 products).
* A **FastAPI backend** with 9 endpoints for KPIs, trends, breakdowns, top products and CSV export. It has a
  shared, validated filter model, a previous-period comparison rule and Pydantic response models (auto-generated
  `/docs`).
* A **Vue 3 + Chart.js frontend** with date presets, filters, KPI cards showing change, a trend chart
  (week/month/quarter), clickable region and category charts (cross-filtering), and a top-10 table with CSV export.
  It is responsive down to phone width.
* **Exports and insights:** CSV/JSON summaries, four static charts and an insights file generated from the data.
* **26 tests:** data integrity, reconciliation of every breakdown to the KPI total, an SQL-injection check, and
  API behaviour (validation errors, grains, limits, CSV, frontend served).

## Results (2025 vs 2024)
* Revenue **£4.07m (+9.5%)**, profit **£1.76m (+10.9%)**, margin **43.3% (+0.6 pts)**.
* Online revenue **+22.1%** vs in-store **-1.5%**; online is now **52%** of revenue.
* Q4 brings about **a third** of annual revenue.
* Electronics: **18.2%** of revenue but **8.6%** of profit (20% margin).
* Orders +12.1% but average order value -2.3%: growth came from more customers ordering, not bigger baskets.

## Skills demonstrated
REST API design · SQL aggregation with parameterised queries · data validation · frontend development with Vue and
Chart.js · dashboard UX (filters, cross-filtering, comparisons) · automated testing · documentation.

## How to run
`pip install -r requirements.txt && pip install -e . && python -m sales_dashboard all && python -m sales_dashboard serve`,
then open http://127.0.0.1:8000.
