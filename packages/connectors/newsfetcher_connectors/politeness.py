"""Polite HTTP client: rate limits, retries, conditional requests, circuit breaker."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from email.utils import formatdate, parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import httpx


@dataclass
class CacheEntry:
    etag: str | None = None
    last_modified: str | None = None
    body: bytes | None = None
    status_code: int = 200
    fetched_at: float = 0.0


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0.0
    last_error: str | None = None


@dataclass
class PolitenessState:
    last_request_at: dict[str, float] = field(default_factory=dict)
    request_timestamps: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    cache: dict[str, CacheEntry] = field(default_factory=dict)
    circuits: dict[str, CircuitState] = field(default_factory=dict)


class PoliteHttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        politeness_delay_ms: int = 1000,
        max_requests_per_minute: int = 10,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        failure_threshold: int = 5,
        circuit_open_seconds: float = 300.0,
        transport_fallback: str | None = None,
        state: PolitenessState | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.politeness_delay_ms = politeness_delay_ms
        self.max_requests_per_minute = max_requests_per_minute
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.circuit_open_seconds = circuit_open_seconds
        self.transport_fallback = transport_fallback
        self.state = state or PolitenessState()
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteHttpClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _host_key(self, url: str) -> str:
        return httpx.URL(url).host or "unknown"

    def _enforce_rate_limit(self, host: str) -> None:
        now = time.monotonic()
        last = self.state.last_request_at.get(host)
        if last is not None:
            elapsed_ms = (now - last) * 1000
            remaining = self.politeness_delay_ms - elapsed_ms
            if remaining > 0:
                time.sleep(remaining / 1000)

        window_start = now - 60
        stamps = [ts for ts in self.state.request_timestamps[host] if ts >= window_start]
        if len(stamps) >= self.max_requests_per_minute:
            sleep_for = 60 - (now - stamps[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            stamps = [ts for ts in stamps if ts >= now - 60]
        stamps.append(now)
        self.state.request_timestamps[host] = stamps
        self.state.last_request_at[host] = now

    def _check_circuit(self, host: str) -> None:
        circuit = self.state.circuits.get(host)
        if circuit and circuit.opened_until > time.monotonic():
            raise RuntimeError(
                f"Circuit open for {host} until {circuit.opened_until:.0f}: {circuit.last_error}"
            )

    def _record_success(self, host: str) -> None:
        self.state.circuits[host] = CircuitState(failures=0, opened_until=0.0)

    def _record_failure(self, host: str, error: str) -> None:
        circuit = self.state.circuits.get(host) or CircuitState()
        circuit.failures += 1
        circuit.last_error = error
        if circuit.failures >= self.failure_threshold:
            circuit.opened_until = time.monotonic() + self.circuit_open_seconds
        self.state.circuits[host] = circuit

    def get(self, url: str, *, use_cache: bool = True) -> httpx.Response:
        host = self._host_key(url)
        self._check_circuit(host)

        headers: dict[str, str] = {}
        cached = self.state.cache.get(url) if use_cache else None
        if cached and cached.etag:
            headers["If-None-Match"] = cached.etag
        if cached and cached.last_modified:
            headers["If-Modified-Since"] = cached.last_modified

        # Prefer urllib when configured — some publishers break httpx (bad Transfer-Encoding).
        if self.transport_fallback == "urllib":
            self._enforce_rate_limit(host)
            try:
                response = self._urllib_get(url)
                if response.status_code < 400:
                    self.state.cache[url] = CacheEntry(
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        body=response.content,
                        status_code=response.status_code,
                        fetched_at=time.time(),
                    )
                self._record_success(host)
                return response
            except Exception as exc:  # noqa: BLE001
                # Fall through to httpx retries below.
                last_error: Exception | None = exc
            else:
                last_error = None
        else:
            last_error = None

        for attempt in range(self.max_retries):
            self._enforce_rate_limit(host)
            try:
                response = self._client.get(url, headers=headers)
                if response.status_code == 304 and cached and cached.body is not None:
                    self._record_success(host)
                    return httpx.Response(
                        status_code=304,
                        headers=response.headers,
                        content=cached.body,
                        request=response.request,
                    )
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if response.status_code < 400:
                    self.state.cache[url] = CacheEntry(
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified")
                        or formatdate(timeval=None, usegmt=True),
                        body=response.content,
                        status_code=response.status_code,
                        fetched_at=time.time(),
                    )
                    # Normalize Last-Modified if upstream sent a parseable date.
                    lm = response.headers.get("Last-Modified")
                    if lm:
                        try:
                            parsedate_to_datetime(lm)
                        except (TypeError, ValueError, IndexError):
                            pass
                    self._record_success(host)
                    return response
                # 4xx: do not retry endlessly; treat as soft failure for circuit only on 429.
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "2"))
                    time.sleep(min(retry_after, 30))
                    continue
                self._record_success(host)
                return response
            except Exception as exc:  # noqa: BLE001 - bounded retry loop
                last_error = exc
                if self._should_urllib_fallback(exc):
                    try:
                        response = self._urllib_get(url)
                        self._record_success(host)
                        return response
                    except Exception as fallback_exc:  # noqa: BLE001
                        last_error = RuntimeError(f"{exc}; urllib fallback: {fallback_exc}")
                time.sleep(min(2**attempt, 8))
        self._record_failure(host, str(last_error))
        raise RuntimeError(f"GET failed for {url}: {last_error}")

    def _should_urllib_fallback(self, exc: Exception) -> bool:
        if self.transport_fallback == "urllib":
            return True
        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "transfer-encoding",
                "remoteprotocolerror",
                "connection reset",
                "incomplete chunked",
            )
        )

    def _urllib_get(self, url: str) -> httpx.Response:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as resp:  # noqa: S310
                content = resp.read()
                status = int(getattr(resp, "status", 200) or 200)
                headers = {k: v for k, v in resp.headers.items()}
                final_url = str(getattr(resp, "geturl", lambda: url)())
        except HTTPError as exc:
            content = exc.read() if hasattr(exc, "read") else b""
            status = int(exc.code)
            headers = dict(getattr(exc, "headers", {}) or {})
            final_url = url
        except URLError as exc:
            raise RuntimeError(str(exc.reason if hasattr(exc, "reason") else exc)) from exc
        return httpx.Response(
            status_code=status,
            headers=headers,
            content=content,
            request=httpx.Request("GET", final_url),
        )

    def content_sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


async def async_sleep_ms(delay_ms: int) -> None:
    await asyncio.sleep(delay_ms / 1000)


def redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    sensitive = {"authorization", "cookie", "set-cookie", "x-api-key"}
    return {k: ("***" if k.lower() in sensitive else v) for k, v in headers.items()}
