# Evidence Map

This file maps the capstone requirements to the implementation and tests.

| Requirement | Implementation | Evidence |
|---|---|---|
| Authenticated widget CRUD | `app/main.py` | `test_health_and_widget_crud` |
| Tenant isolation | `require_tenant()` + owner-scoped widget queries | Widget access code and review |
| One-line embed snippet | `GET /api/widgets/{id}/embed` and `/widget.js` | CRUD test checks generated `<script>` |
| Cross-origin public submission | CORS middleware + public submission route | `test_cross_origin_submission_and_side_effect_failure_do_not_break_it`, `test_cors_preflight` |
| Validation / 4xx | Pydantic constraints + empty submission check | `test_invalid_payload_rejected`, `test_oversized_payload_rejected` |
| Rate limiting / 429 | In-memory per-IP sliding window | `test_rate_limit_returns_429` |
| Honeypot | `website` hidden field | `test_honeypot_rejected` |
| Geo provider A/B fallback | `geo_lookup()` tries A then B | `test_geo_provider_b_is_used_when_a_fails` |
| Geo total outage does not fail submission | `geo_lookup()` returns `unavailable` | `test_geo_total_outage_is_non_fatal` plus public submit path |
| Side-effect failure isolation | `send_side_effects()` catches failures after persistence | `test_cross_origin_submission_and_side_effect_failure_do_not_break_it` |
| Dashboard | summary, widget stats, geo endpoints | API implementation in `app/main.py` |
| Tests | pytest suite | `tests/test_capstone.py`, `tests/test_geo.py` |

## Verification note

The repository now includes a GitHub Actions CI workflow and a complete local test suite covering the required failure modes. External provider credentials are intentionally not fabricated; geo fallback is tested with controlled provider failures, while the webhook failure path uses an unreachable local endpoint.
