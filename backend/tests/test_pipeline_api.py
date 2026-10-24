"""End-to-end: a demo pipeline run, then every API route against it."""

from fastapi.testclient import TestClient


def test_snapshot_shape(demo_db):
    _, p = demo_db
    assert p["meta"]["mode"] == "demo"
    for key in ("regime", "movers", "heatmap", "numbers", "curves", "spreads", "policy", "inflation", "regions",
                "relationships", "interview", "flashcards", "panels", "curve_shapes"):
        assert key in p, key
    assert len(p["regime"]["paragraph"].split()) <= 100
    assert all(len(r["text"].split()) <= 60 for r in p["regions"])
    assert len(p["movers"]["up"]) <= 5 and len(p["movers"]["down"]) <= 5
    assert len(p["interview"]) == 5 and all(q["answer"] for q in p["interview"])
    assert len(p["flashcards"]) == 5
    assert {r["region"] for r in p["heatmap"]["rows"]} == {"US", "UK", "EA", "JP", "CN"}
    assert {c["id"] for c in p["curves"]} >= {"US_2s10s", "UK_5s30s", "DE_2s10s", "JP_10s30s"}
    assert {s["id"] for s in p["spreads"]} >= {"US10_DE10", "IT10_DE10", "JP2_DE2"}
    banks = {b["id"]: b for b in p["policy"]}
    assert set(banks) == {"FED", "BOE", "ECB", "BOJ"}
    assert banks["FED"]["summary"]["priced_12m_bp"] < 0 and banks["BOJ"]["summary"]["priced_12m_bp"] > 0
    assert p["regime"]["name"] == "Hawkish repricing"   # the demo's scripted day


def test_api(demo_db):
    from macrodash.api.app import app
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    r = c.get("/api/dashboard")
    assert r.status_code == 200 and r.headers.get("etag")
    assert c.get("/api/dashboard", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    for sid in ("US10Y", "US_2s10s", "IT10_DE10", "US_5y5y", "PRICING_FED_12M"):
        body = c.get(f"/api/series/{sid}?range=3M").json()
        assert body["points"] and body["range_stats"]["n"] > 10, sid
    assert c.get("/api/series/US10Y?range=10Y").status_code == 400
    assert c.get("/api/series/NOPE").status_code == 404
    multi = c.get("/api/series?ids=US10Y,DE10Y&range=1M").json()
    assert len(multi["series"]) == 2
    due = c.get("/api/flashcards/due").json()
    assert due["cards"]
    cid = due["cards"][0]["id"]
    rev = c.post(f"/api/flashcards/{cid}/review", json={"grade": 4}).json()
    assert rev["interval_days"] == "1"
    assert c.post("/api/flashcards/x/review", json={"grade": 9}).status_code == 422
    assert c.post("/api/admin/refresh").status_code == 403
