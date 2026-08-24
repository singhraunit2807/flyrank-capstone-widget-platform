import httpx
import pytest

from app import main


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        result = self.responses[url]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


@pytest.mark.asyncio
async def test_geo_provider_b_is_used_when_a_fails(monkeypatch):
    monkeypatch.setenv("GEO_PROVIDER_A_URL", "provider-a")
    monkeypatch.setenv("GEO_PROVIDER_B_URL", "provider-b")
    request = httpx.Request("GET", "https://provider-a")
    responses = {"provider-a": httpx.ConnectError("provider A down", request=request), "provider-b": {"country": "India", "city": "Delhi"}}
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda timeout: FakeClient(responses))

    result = await main.geo_lookup("127.0.0.1")
    assert result == ("India", "Delhi", "provider")


@pytest.mark.asyncio
async def test_geo_total_outage_is_non_fatal(monkeypatch):
    monkeypatch.setenv("GEO_PROVIDER_A_URL", "provider-a")
    monkeypatch.setenv("GEO_PROVIDER_B_URL", "provider-b")
    request = httpx.Request("GET", "https://provider-a")
    failure = httpx.ConnectError("provider down", request=request)
    responses = {"provider-a": failure, "provider-b": failure}
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda timeout: FakeClient(responses))

    result = await main.geo_lookup("127.0.0.1")
    assert result == ("", "", "unavailable")
