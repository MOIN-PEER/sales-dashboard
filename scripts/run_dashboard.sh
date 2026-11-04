#!/usr/bin/env bash
# macOS/Linux: build data, export results and start the dashboard
set -e
source .venv/bin/activate
python -m sales_dashboard all
python -m sales_dashboard serve
