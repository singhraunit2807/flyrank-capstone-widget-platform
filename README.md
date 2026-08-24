# Embeddable Widget & Lead-Capture Platform

A small multi-tenant backend that lets customers create embeddable lead-capture widgets and receive submissions from other origins.

## What it does

- Authenticated widget CRUD with tenant isolation
- Public one-line embed snippet
- Cross-origin submission API with CORS and validation
- Honeypot spam protection
- Per-IP rate limiting
- IP geolocation with provider-A/provider-B fallback
- Best-effort email/webhook side effects that do not break the main submission
- Owner dashboard APIs for submissions, counts, widget stats and geography
- Automated tests for the required failure modes

## Stack

Python, FastAPI, SQLite by default, SQLAlchemy, Pydantic, httpx, pytest.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API docs.

## Configuration

Copy `.env.example` to `.env` when using external services. The default local setup works without external credentials.

The geo adapters use `GEO_PROVIDER_A_URL` first and `GEO_PROVIDER_B_URL` as fallback. If both are unavailable, the submission is still stored with `geo_status=unavailable`.

Email/webhook delivery is best-effort. A side-effect failure is recorded but does not turn a successful submission into a 5xx response.

## Authentication

The demo API uses a bearer token mapped to a tenant in the local database. Seeded credentials are documented in `app/seed.py` for local development only.

Do not use the demo token in production.

## Embed flow

Create a widget through the authenticated API, then request its public embed snippet. The generated script loads the widget configuration and posts submissions to the public endpoint.

```html
<script src="http://127.0.0.1:8000/widget.js?id=YOUR_WIDGET_ID"></script>
```

For a deployed environment, replace the origin with the public HTTPS domain.

## Public submission

`POST /api/public/widgets/{widget_id}/submissions`

Example:

```json
{
  "name": "Demo User",
  "email": "demo@example.com",
  "message": "Please contact me",
  "website": ""
}
```

The `website` field is the honeypot. A non-empty value is treated as spam and returns `400`.

## Dashboard

Authenticated endpoints include:

- `GET /api/widgets`
- `GET /api/widgets/{id}/submissions`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/widgets/{id}`
- `GET /api/dashboard/geo`

## Testing

```bash
pytest -q
```

The suite covers widget CRUD, cross-origin CORS, valid submissions, validation and oversized payloads, rate limiting, honeypot protection, geo provider fallback, total geo outage, and side-effect failure isolation.

## Transparency

This repository is a reconstructed implementation based on the provided capstone specification. External providers are kept behind adapters and are not claimed to be live without credentials. The local mode is fully runnable without paid services.
