@echo off
REM Windows: build data, export results and start the dashboard
call .venv\Scripts\activate
python -m sales_dashboard all
python -m sales_dashboard serve
