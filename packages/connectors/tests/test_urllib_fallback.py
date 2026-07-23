from __future__ import annotations

from newsfetcher_connectors import politeness
from newsfetcher_connectors.politeness import PoliteHttpClient


def test_urllib_response_keeps_final_request_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/html"}

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"<html>ok</html>"

        def geturl(self) -> str:
            return "https://www.kuna.net.kw/Default.aspx?language=en"

    monkeypatch.setattr(politeness, "urlopen", lambda *args, **kwargs: FakeResponse())
    client = PoliteHttpClient(
        user_agent="NewsFetcherBot/0.1 (+test)",
        politeness_delay_ms=0,
        max_requests_per_minute=60,
    )
    try:
        response = client._urllib_get("https://www.kuna.net.kw/")
        assert str(response.url) == (
            "https://www.kuna.net.kw/Default.aspx?language=en"
        )
    finally:
        client.close()


def test_urllib_fallback_fetches_kuna_homepage() -> None:
    client = PoliteHttpClient(
        user_agent="NewsFetcherBot/0.1 (+test)",
        politeness_delay_ms=0,
        max_requests_per_minute=60,
        transport_fallback="urllib",
        timeout_seconds=25.0,
    )
    try:
        response = client.get("https://www.kuna.net.kw/", use_cache=False)
        assert response.status_code == 200
        assert len(response.content) > 1000
        assert b"html" in response.content[:200].lower()
    finally:
        client.close()
