import os

os.environ["RATE_LIMIT_REQUESTS"] = "3"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
os.environ["WEBHOOK_URL"] = "http://127.0.0.1:9/unavailable"

from fastapi.testclient import TestClient

from app.main import app, SessionLocal, Tenant, Widget, Base, engine, _rate_windows
from sqlalchemy import select

client = TestClient(app)
TOKEN = "demo-token-change-me"


def widget_id():
    with SessionLocal() as db:
        widget = db.scalar(select(Widget))
        if not widget:
            from uuid import uuid4
            tenant = db.scalar(select(Tenant))
            widget = Widget(id=str(uuid4()), tenant_id=tenant.id, name="Test Widget", title="Contact", fields_json='["name","email","message"]')
            db.add(widget); db.commit(); db.refresh(widget)
        return widget.id


def test_health_and_widget_crud():
    assert client.get("/").status_code == 200
    headers = {"Authorization": f"Bearer {TOKEN}"}
    created = client.post("/api/widgets", headers=headers, json={"name":"Demo Widget","title":"Talk to us","fields":["name","email"]})
    assert created.status_code == 200
    wid = created.json()["id"]
    assert client.get("/api/widgets", headers=headers).status_code == 200
    assert client.patch(f"/api/widgets/{wid}", headers=headers, json={"name":"Updated Widget","title":"Hello","fields":["email"]}).status_code == 200
    assert client.get(f"/api/widgets/{wid}/embed", headers=headers).json()["script"].startswith("<script")


def test_cross_origin_submission_and_side_effect_failure_do_not_break_it():
    _rate_windows.clear()
    wid = widget_id()
    response = client.post(
        f"/api/public/widgets/{wid}/submissions",
        headers={"Origin":"https://customer.example"},
        json={"name":"Alice","email":"alice@example.com","message":"Hello","website":""},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["side_effect_status"] == "webhook_failed"


def test_honeypot_rejected():
    _rate_windows.clear(); wid = widget_id()
    r = client.post(f"/api/public/widgets/{wid}/submissions", json={"email":"spam@example.com","message":"x","website":"bot"})
    assert r.status_code == 400


def test_invalid_payload_rejected():
    _rate_windows.clear(); wid = widget_id()
    r = client.post(f"/api/public/widgets/{wid}/submissions", json={"name":"","email":"","message":"","website":""})
    assert r.status_code == 422


def test_rate_limit_returns_429():
    _rate_windows.clear(); wid = widget_id()
    for _ in range(3):
        client.post(f"/api/public/widgets/{wid}/submissions", json={"email":"x@example.com","message":"hello","website":""})
    r = client.post(f"/api/public/widgets/{wid}/submissions", json={"email":"x@example.com","message":"hello","website":""})
    assert r.status_code == 429


def test_cors_preflight():
    _rate_windows.clear(); wid = widget_id()
    r = client.options(f"/api/public/widgets/{wid}/submissions", headers={"Origin":"https://customer.example","Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"content-type"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"
