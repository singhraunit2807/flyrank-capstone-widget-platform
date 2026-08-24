# Evidence Map

This file maps the capstone requirements to the implementation and tests.

| Requirement | Implementation | Evidence |
|---|---|---|
| Authenticated widget CRUD | `app/main.py` | `test_health_and_widget_crud` |
| Tenant isolation | `require_tenant()` + owner-scoped widget queries | Widget access tests and code review |
| One-line embed snippet | `GET /api/widgets/{id}/embed` and `/widget.js` | CRUD test checks generated `<script>` |
| Cross-origin public submission | CORS middleware + public submission route | `test_cross_origin_submission_and_side_effect_failure_do_not_break_it`, `test_cors_preflight` |
| Validation / 4xx | Pydantic constraints + empty submission check | `test_invalid_payload_rejected` |
| Rate limiting / 429 | In-memory per-IP sliding window | `test_rate_limit_returns_429` |
| Honeypot | `website` hidden field | `test_honeypot_rejected` |
| Geo provider A/B fallback | `geo_lookup()` tries A then B | Code path in `app/main.py`; production evidence requires configured provider URLs |
| Geo total outage does not fail submission | `geo_lookup()` returns `unavailable` | Local no-provider path is non-fatal |
| Side-effect failure isolation | `send_side_effects()` catches failures after persistence | `test_cross_origin_submission_and_side_effect_failure_do_not_break_it` |
| Dashboard | summary, widget stats, geo endpoints | API implementation in `app/main.py` |
| Tests | pytest suite | `tests/test_capstone.py` |

## Honest verification note

The local default setup is runnable without external provider credentials. Real provider A/B behavior and live email/webhook delivery require URLs/credentials in `.env`; those are intentionally not fabricated. The test suite proves the failure-isolation behavior using a deliberately unreachable webhook and the no-provider geo path.
