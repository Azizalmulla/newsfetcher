from __future__ import annotations

from newsfetcher_connectors.html import HtmlConnector
from newsfetcher_connectors.types import ConnectorContext


class _FakeResponse:
    def __init__(self, text: str, url: str = "https://www.alqabas.com/") -> None:
        self.status_code = 200
        self.text = text
        self.content = text.encode("utf-8")
        self._url = url

    @property
    def url(self) -> str:
        raise RuntimeError("response.url should not be required for HTML discovery")


class _FakeClient:
    def get(self, url: str) -> _FakeResponse:  # noqa: ARG002
        html = """
        <html><body>
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"homeData":{"items":[
          {"id":"123","title":"Hello Kuwait","slug":"hello-kuwait"}
        ]}}}}
        </script>
        <a href="/article/999/other">Other article title here</a>
        </body></html>
        """
        return _FakeResponse(html)

    def close(self) -> None:
        return None

    def content_sha256(self, content: bytes) -> str:
        return "hash"


def test_html_connector_parses_next_data_articles(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    connector = HtmlConnector()
    monkeypatch.setattr(connector, "_http", lambda context: _FakeClient())
    result = connector.discover(
        ConnectorContext(
            publisher_code="alqabas",
            channel_code="web_ar",
            base_url="https://www.alqabas.com",
            language="ar",
            config={
                "listing_urls": ["https://www.alqabas.com/"],
                "parse_next_data": True,
                "path_regex": r"^/article/\d+",
                "max_urls": 20,
            },
        )
    )
    urls = {item.source_url for item in result.items}
    assert any("/article/123/" in url for url in urls)
    assert result.meta["next_data_items"] >= 1
