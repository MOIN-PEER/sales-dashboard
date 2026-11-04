"""Command line:

    python -m sales_dashboard build    # (re)create data/sales.db from the generator
    python -m sales_dashboard export   # write results and charts to outputs/
    python -m sales_dashboard serve    # start the API + dashboard on http://127.0.0.1:8000
    python -m sales_dashboard all      # build + export
"""

import sys

from .config import DATABASE_PATH


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd not in {"build", "export", "serve", "all"}:
        sys.exit(__doc__)
    if cmd in ("build", "all"):
        from .generate_data import build_database
        info = build_database(DATABASE_PATH)
        print(f"Built {info['path']}: {info['sales_lines']:,} sales lines, {info['products']} products")
    if cmd in ("export", "all"):
        from .export_results import export
        s = export()["year_2025"]
        print(f"2025 revenue £{s['revenue']:,.0f} ({s['change_pct']['revenue']:+}% vs 2024), "
              f"margin {s['margin_pct']}%. Results written to outputs/")
    if cmd == "serve":
        import uvicorn
        print("Dashboard: http://127.0.0.1:8000    API docs: http://127.0.0.1:8000/docs")
        uvicorn.run("sales_dashboard.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
