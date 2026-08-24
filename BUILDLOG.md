# Build Log

## 1. Project skeleton

Created a FastAPI application with SQLite persistence, environment configuration, and a small automated test suite.

## 2. Widget management

Added tenant-aware widget creation, listing, update, delete, and embed-snippet generation. Owner queries always scope widgets by the authenticated tenant.

## 3. Public embed and submission

Added a generated one-line script and a public submission endpoint designed for use from a different origin. CORS is enabled and request validation returns 4xx errors for invalid data.

## 4. Protection

Added a per-IP sliding-window limiter that returns `429` with `Retry-After`, plus a hidden honeypot field for simple bot/spam detection.

## 5. Enrichment

Added provider-A/provider-B geo lookup with timeout and fallback. If both providers are unavailable, the submission is still persisted with an unavailable geo status.

## 6. Side effects

Added a best-effort webhook adapter. The database write happens before the side effect, and failures are captured as `webhook_failed` instead of changing the successful submission into a server error.

## 7. Dashboard

Added owner-scoped submission listing, total counts, per-widget counts, and country aggregation.

## 8. Verification

Added tests for CRUD, cross-origin CORS preflight, validation, rate limiting, honeypot rejection, and side-effect failure isolation. External geo providers are left configurable rather than replaced with fake credentials.

## Current limitation

The default repository runs locally. A public HTTPS deployment and real provider credentials are required for a true external-site embed and live geo/webhook integrations.
