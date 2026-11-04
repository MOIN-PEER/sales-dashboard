"""API contract tests with FastAPI's TestClient (no server needed)."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_filters_lists_options(client):
    body = client.get("/api/filters").json()
    assert "London" in body["regions"] and body["channels"] == ["In-store", "Online"]
    assert body["min_date"] == "2024-01-01"


def test_kpis_with_filters(client):
    r = client.get("/api/kpis", params={"start": "2025-01-01", "end": "2025-12-31", "region": "Wales"})
    assert r.status_code == 200
    body = r.json()
    assert body["revenue"] > 0 and body["previous_period"]["start"] == "2024-01-01"


def test_unknown_region_is_rejected(client):
    r = client.get("/api/kpis", params={"region": "Atlantis"})
    assert r.status_code == 400 and "Unknown region" in r.json()["detail"]


def test_start_after_end_is_rejected(client):
    assert client.get("/api/kpis", params={"start": "2025-05-01", "end": "2025-04-01"}).status_code == 400


def test_bad_date_and_grain_give_422(client):
    assert client.get("/api/kpis", params={"start": "not-a-date"}).status_code == 422
    assert client.get("/api/revenue-trend", params={"grain": "decade"}).status_code == 422


def test_trend_grains(client):
    months = client.get("/api/revenue-trend", params={"grain": "month"}).json()
    quarters = client.get("/api/revenue-trend", params={"grain": "quarter"}).json()
    assert len(months) == 24 and len(quarters) == 8
    assert quarters[0]["period"] == "2024-Q1"


def test_top_products_limit_validation(client):
    assert len(client.get("/api/top-products", params={"limit": 3}).json()) == 3
    assert client.get("/api/top-products", params={"limit": 0}).status_code == 422


def test_csv_export(client):
    r = client.get("/api/export/products.csv", params={"category": "Beauty"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("product_id,product_name") and len(lines) == 9   # header + 8 Beauty products


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Sales Performance Dashboard" in r.text
