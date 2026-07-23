"""Fetch and parse article HTML bodies after discovery."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from newsfetcher_connectors.politeness import PoliteHttpClient
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.arabic import normalize_text
from app.models.articles import Article, ArticleImage, ArticleVersion

_META_DATE_KEYS = (
    "article:published_time",
    "og:published_time",
    "pubdate",
    "publish-date",
    "date",
    "DC.date.issued",
)

# Nav / chrome snippets that must never be stored as article bodies.
_JUNK_BODY_MARKERS = (
    "عدد اليوم",
    "ماستر كلاس",
    "أرشيف القبس",
    "كتاب القبس",
    "معرض الصور",
)

_MIN_BODY_CHARS = 80
_KUWAIT_UTC_OFFSET = timedelta(hours=3)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


def _parse_kuwait_naive_datetime(raw: str | None) -> datetime | None:
    """CMS clocks without TZ are Asia/Kuwait (+03), not UTC."""
    if not raw:
        return None
    text = raw.strip()
    if re.search(r"(Z|[+-]\d{2}:?\d{2})$", text, flags=re.I):
        return _parse_datetime(text)
    m = re.match(r"(20\d{2})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", text)
    if m:
        local = datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
            int(m.group(6)),
            tzinfo=UTC,
        )
        return local - _KUWAIT_UTC_OFFSET
    return _parse_datetime(text)


def _html_or_text_to_plain(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        content = "\n\n".join(str(part) for part in content if part)
    text = str(content).strip()
    if not text:
        return ""
    if "<" in text or "&" in text:
        return BeautifulSoup(text, "lxml").get_text("\n", strip=True)
    return text


def _image_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            candidate = _image_value(item)
            if candidate:
                return candidate
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "src", "sourceUrl"):
            candidate = _image_value(value.get(key))
            if candidate:
                return candidate
    return None


def _extract_primary_image(html_text: str, *, page_url: str) -> str | None:
    """Extract a publisher-provided article cover, preferring explicit social metadata."""
    soup = BeautifulSoup(html_text, "lxml")
    candidates: list[str] = []
    meta_attrs: tuple[dict[str, Any], ...] = (
        {"property": "og:image:secure_url"},
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
    )
    for attrs in meta_attrs:
        node = soup.find("meta", attrs=attrs)
        if node and node.get("content"):
            candidates.append(str(node["content"]))

    image_link = soup.find("link", rel=lambda value: value and "image_src" in value)
    if image_link and image_link.get("href"):
        candidates.append(str(image_link["href"]))

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json_ld(payload):
            candidate = _image_value(item.get("image") or item.get("thumbnailUrl"))
            if candidate:
                candidates.append(candidate)

    for raw in candidates:
        absolute = urljoin(page_url, unescape(raw.strip()))
        parsed = urlparse(absolute)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return absolute[:2048]
    return None


def is_junk_body(body: str | None) -> bool:
    """Reject navigation chrome and other non-article blobs."""
    text = (body or "").strip()
    if not text:
        return True
    hits = sum(1 for marker in _JUNK_BODY_MARKERS if marker in text)
    if hits >= 3:
        return True
    if len(text) < _MIN_BODY_CHARS and hits >= 1:
        return True
    return False


def body_quality_ok(body: str | None) -> bool:
    text = (body or "").strip()
    return len(text) >= _MIN_BODY_CHARS and not is_junk_body(text)


def _extract_next_data_article(html_text: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, flags=re.S
    )
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    article = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("article")
    )
    if not isinstance(article, dict):
        return {}
    content = article.get("content") or article.get("body") or ""
    body = _html_or_text_to_plain(content)
    return {
        "title": article.get("title"),
        "body": body,
        "published_at": _parse_datetime(str(article.get("date") or "") or None),
        "paid_article": bool(article.get("paidArticle")),
        # Only claim next_data when the body is actually usable.
        "source": "next_data" if body_quality_ok(body) else None,
    }


def _extract_embedded_article_info(html_text: str) -> dict[str, Any]:
    """Al-Seyassah / Al-Rai CMS: body lives in `var article_info = {...}` (Vue stub page)."""
    match = re.search(r"var\s+article_info\s*=\s*(\{.*?\});\s*", html_text, flags=re.S)
    if not match:
        return {}
    try:
        info = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    if not isinstance(info, dict):
        return {}
    body = _html_or_text_to_plain(
        info.get("article_body") or info.get("article_content") or info.get("body")
    )
    title = (info.get("article_title") or info.get("seo_meta_title") or "").strip() or None
    published_at = _parse_kuwait_naive_datetime(
        str(info.get("publish_time") or info.get("max_publish_time") or "") or None
    )
    return {
        "title": title,
        "body": body,
        "published_at": published_at,
        "paid_article": False,
        "source": "article_info" if body_quality_ok(body) or title else None,
    }


def _walk_json_ld(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        if "@graph" in node and isinstance(node["@graph"], list):
            out: list[dict[str, Any]] = []
            for item in node["@graph"]:
                out.extend(_walk_json_ld(item))
            return out
        return [node]
    if isinstance(node, list):
        out = []
        for item in node:
            out.extend(_walk_json_ld(item))
        return out
    return []


def _extract_json_ld_article(html_text: str) -> dict[str, Any]:
    """Prefer schema.org NewsArticle.articleBody (Al-Rai ships full text here)."""
    soup = BeautifulSoup(html_text, "lxml")
    best: dict[str, Any] = {}
    best_len = 0
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _walk_json_ld(payload):
            types = item.get("@type")
            type_names = (
                [types]
                if isinstance(types, str)
                else [t for t in types if isinstance(t, str)]
                if isinstance(types, list)
                else []
            )
            if not any(t in {"NewsArticle", "Article"} for t in type_names):
                continue
            body = _html_or_text_to_plain(item.get("articleBody"))
            if len(body) < best_len and best:
                continue
            best_len = len(body)
            best = {
                "title": (item.get("headline") or "").strip() or None,
                "body": body,
                "published_at": _parse_datetime(
                    str(item.get("datePublished") or item.get("dateCreated") or "")
                    or None
                ),
                "paid_article": False,
                "source": "json_ld" if body_quality_ok(body) else None,
            }
    return best


def extract_alqabas_api_article(
    article_id: str,
    client: PoliteHttpClient,
) -> dict[str, Any]:
    """Al-Qabas SSR leaves content empty; body comes from their elastic API."""
    response = client.get(
        f"https://api.alqabas.com/api/article/elastic/{article_id}"
    )
    if response.status_code >= 400:
        raise RuntimeError(f"alqabas api HTTP {response.status_code}")
    payload = response.json()
    result = (payload.get("data") or {}).get("result") or {}
    if not isinstance(result, dict):
        return {}
    body = _html_or_text_to_plain(result.get("content") or "")
    return {
        "title": (result.get("title") or "").strip() or None,
        "body": body,
        "image_url": _image_value(
            result.get("image")
            or result.get("mainImage")
            or result.get("featuredImage")
            or result.get("thumbnail")
        ),
        "published_at": _parse_datetime(
            str(result.get("publishDate") or result.get("date") or "") or None
        ),
        "paid_article": bool(result.get("paidArticle")),
        "char_count": len(body),
        "body_source": "alqabas_api" if body else None,
        "used_next_data": False,
        "date_unknown": _parse_datetime(
            str(result.get("publishDate") or result.get("date") or "") or None
        )
        is None,
    }


def alqabas_article_id(url: str) -> str | None:
    match = re.search(r"/article/(\d+)", url)
    return match.group(1) if match else None


def _parse_dd_mm_yyyy(raw: str) -> datetime | None:
    """Parse day-first dates: 22/07/2026, 22/07/2026 09:28, 21-7-2026."""
    text = (raw or "").strip()
    m = re.search(
        r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})(?:\s+(\d{1,2}):(\d{2}))?\b",
        text,
    )
    if not m:
        return None
    try:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4) or 0)
        minute = int(m.group(5) or 0)
        return datetime(year, month, day, hour, minute, tzinfo=UTC)
    except ValueError:
        return None


def _parse_yyyy_mm_dd(raw: str) -> datetime | None:
    """Parse year-first dates: 2026/07/20 (Al-Watan WriterLink)."""
    text = (raw or "").strip()
    m = re.search(r"\b(20\d{2})[/.-](\d{1,2})[/.-](\d{1,2})\b", text)
    if not m:
        return None
    try:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC
        )
    except ValueError:
        return None


def _extract_page_published_at(soup: BeautifulSoup, html_text: str) -> datetime | None:
    """Prefer explicit article date labels; ignore sitewide 'today' headers."""
    # Al-Wasat article date
    for el in soup.find_all(id=re.compile(r"ContentPlaceHolder1_lblDate$", re.I)):
        parsed = _parse_dd_mm_yyyy(el.get_text(" ", strip=True))
        if parsed is not None:
            return parsed

    # Al-Watan article date lives in font.WriterLink as yyyy/mm/dd (+ separate time node).
    writer_links = soup.select("font.WriterLink")
    if writer_links:
        date_part = None
        time_part = None
        for el in writer_links:
            text = el.get_text(" ", strip=True)
            if re.fullmatch(r"20\d{2}[/.-]\d{1,2}[/.-]\d{1,2}", text):
                date_part = _parse_yyyy_mm_dd(text)
            elif re.fullmatch(r"\d{1,2}:\d{2}\s*[صمم]?\.?", text) or re.search(
                r"\d{1,2}:\d{2}", text
            ):
                tm = re.search(r"(\d{1,2}):(\d{2})", text)
                if tm:
                    hour, minute = int(tm.group(1)), int(tm.group(2))
                    # Arabic PM marker م
                    if "م" in text and hour < 12:
                        hour += 12
                    if "ص" in text and hour == 12:
                        hour = 0
                    time_part = (hour, minute)
        if date_part is not None:
            if time_part is not None:
                return date_part.replace(hour=time_part[0], minute=time_part[1])
            return date_part

    for el in soup.find_all(id=re.compile(r"(^|_)lblDate$", re.I)):
        # Skip empty / cartoon widget dates
        parsed = _parse_dd_mm_yyyy(el.get_text(" ", strip=True))
        if parsed is not None:
            return parsed

    # Do NOT use ctl00_lblGrogerianDate — that is the site's "today" header.

    # Fallback: first day-first Gregorian date in page body (not Hijri 14xx).
    for match in re.finditer(
        r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})(?:\s+(\d{1,2}):(\d{2}))?\b",
        html_text,
    ):
        # Skip matches that are clearly the site header (same line as هـ / م alone)
        start = max(0, match.start() - 40)
        ctx = html_text[start : match.end() + 20]
        if "lblGrogerianDate" in ctx or "lblGregorianDate" in ctx or "lblHijriDate" in ctx:
            continue
        parsed = _parse_dd_mm_yyyy(match.group(0))
        if parsed is not None:
            return parsed

    for match in re.finditer(r"\b(20\d{2})[/.-](\d{1,2})[/.-](\d{1,2})\b", html_text):
        parsed = _parse_yyyy_mm_dd(match.group(0))
        if parsed is not None:
            return parsed
    return None


def extract_article_content(html: bytes, *, url: str) -> dict[str, Any]:
    html_text = html.decode("utf-8", errors="ignore")
    image_url = _extract_primary_image(html_text, page_url=url)
    next_data = _extract_next_data_article(html_text)
    article_info = _extract_embedded_article_info(html_text)
    json_ld = _extract_json_ld_article(html_text)

    soup = BeautifulSoup(html, "lxml")
    # Keep a copy for date labels before chrome stripping.
    date_soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
        tag.decompose()

    title = (
        next_data.get("title")
        or article_info.get("title")
        or json_ld.get("title")
    )
    og_title = soup.find("meta", property="og:title")
    if not title and og_title and og_title.get("content"):
        title = str(og_title["content"]).strip()
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if not title and h1:
        title = h1.get_text(" ", strip=True)

    published_at = (
        next_data.get("published_at")
        or article_info.get("published_at")
        or json_ld.get("published_at")
    )
    if published_at is None:
        for key in _META_DATE_KEYS:
            meta = soup.find("meta", attrs={"property": key}) or soup.find(
                "meta", attrs={"name": key}
            )
            if meta and meta.get("content"):
                published_at = _parse_datetime(str(meta["content"]))
                if published_at:
                    break
    if published_at is None:
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el is not None:
            published_at = _parse_datetime(str(time_el.get("datetime")))

    if published_at is None:
        path = urlparse(url).path
        match = re.search(r"(20\d{2})[-/](\d{2})[-/](\d{2})", path)
        if match:
            published_at = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=UTC
            )

    visible_date = _extract_page_published_at(date_soup, html_text)
    if visible_date is not None:
        if published_at is None or published_at < visible_date - timedelta(days=30):
            published_at = visible_date

    # Discard absurdly old meta dates (broken CMS fields).
    if published_at is not None and published_at.year < datetime.now(UTC).year - 1:
        published_at = visible_date

    # Prefer structured CMS payloads over DOM scrapes (sidebar noise on Al-Rai).
    body = ""
    body_source = None
    for candidate, source in (
        (next_data.get("body"), "next_data"),
        (article_info.get("body"), "article_info"),
        (json_ld.get("body"), "json_ld"),
    ):
        text = (candidate or "").strip()
        if body_quality_ok(text):
            body = text
            body_source = source
            break
        if text and not body:
            body = text
            body_source = source

    if not body_quality_ok(body):
        body_node = (
            soup.find("article")
            or soup.find("div", class_=re.compile(r"(article|story|content|post).*body", re.I))
            or soup.find("div", id=re.compile(r"(article|story|content)", re.I))
            or soup.find("main")
            or soup.body
        )
        paragraphs: list[str] = []
        if body_node is not None:
            for p in body_node.find_all("p"):
                text = p.get_text(" ", strip=True)
                if len(text) >= 40:
                    paragraphs.append(text)
        dom_body = "\n\n".join(paragraphs).strip()
        if not dom_body and body_node is not None:
            dom_body = body_node.get_text("\n", strip=True)[:20000]
        if body_quality_ok(dom_body) or len(dom_body) > len(body or ""):
            body = dom_body
            body_source = "dom"

    if is_junk_body(body):
        body = ""
        body_source = None

    return {
        "title": title,
        "body": body,
        "image_url": image_url,
        "published_at": published_at,
        "char_count": len(body or ""),
        "paid_article": bool(next_data.get("paid_article")),
        "used_next_data": bool(next_data.get("source")),
        "body_source": body_source,
        "date_unknown": published_at is None,
    }


def archive_year_from_url(url: str) -> int | None:
    """Al-Watan embeds archive quarters like yearquarter=20161 (=2016 Q1)."""
    raw = unescape(url)
    match = re.search(r"[?&]yearquarter=(\d{4,})", raw, flags=re.I)
    if not match:
        return None
    token = match.group(1)
    try:
        return int(token[:4])
    except ValueError:
        return None


def invalidate_junk_bodies(db: Session) -> dict[str, Any]:
    """Clear stored nav/chrome blobs so they can be re-fetched."""
    articles = list(
        db.scalars(select(Article).where(Article.body_original.is_not(None))).all()
    )
    cleared = 0
    for article in articles:
        if is_junk_body(article.body_original):
            article.body_original = None
            article.body_normalized = None
            article.fetched_at = None
            article.metadata_ = {
                **(article.metadata_ or {}),
                "fetch": {
                    "ok": False,
                    "invalidated": "junk_body",
                    "char_count": 0,
                },
            }
            cleared += 1
    db.commit()
    return {"scanned": len(articles), "cleared": cleared}


def _should_replace_body(existing: str | None, new_body: str) -> bool:
    """Never let a worse/empty result overwrite a good body (concurrent jobs)."""
    if body_quality_ok(new_body):
        return True
    if not body_quality_ok(existing):
        return True
    return False


def fetch_article_bodies(
    db: Session,
    *,
    lookback_days: int | None = 5,
    limit: int = 200,
    politeness_delay_ms: int = 800,
    max_requests_per_minute: int = 40,
    commit_every: int = 25,
    use_browser_fallback: bool = True,
    refetch_junk: bool = True,
) -> dict[str, Any]:
    if refetch_junk:
        invalidate_junk_bodies(db)

    stmt = (
        select(Article)
        .where(
            or_(
                Article.body_original.is_(None),
                # Empty string leftovers
                Article.body_original == "",
            )
        )
        .order_by(Article.discovered_at.desc())
        .limit(limit)
    )
    articles = list(db.scalars(stmt).all())
    # Skip already-classified out-of-window empties so they don't loop forever.
    articles = [
        a
        for a in articles
        if not (a.metadata_ or {}).get("stale_outside_lookback")
    ]
    client = PoliteHttpClient(
        user_agent=(
            "NewsFetcherBot/0.1 (+https://newsfetcher.local; media-monitoring; "
            "contact=ops@newsfetcher.local)"
        ),
        politeness_delay_ms=politeness_delay_ms,
        max_requests_per_minute=max_requests_per_minute,
        timeout_seconds=25.0,
        transport_fallback="urllib",
    )
    fetched = 0
    stale_dropped = 0
    browser_fetches = 0
    api_fetches = 0
    skipped_overwrite = 0
    errors: list[str] = []
    since_commit = 0
    cutoff = None
    if lookback_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    try:
        for article in articles:
            try:
                source_url = unescape(article.source_url or "")
                host = urlparse(source_url).netloc.lower().removeprefix("www.")

                archive_year = archive_year_from_url(source_url)
                if archive_year is not None and archive_year < datetime.now(UTC).year - 1:
                    article.metadata_ = {
                        **(article.metadata_ or {}),
                        "stale_outside_lookback": True,
                        "parsed_published_at": f"{archive_year}-01-01T00:00:00+00:00",
                        "archive_yearquarter": True,
                    }
                    stale_dropped += 1
                    since_commit += 1
                    if since_commit >= commit_every:
                        db.commit()
                        since_commit = 0
                    continue

                parsed: dict[str, Any]
                if host == "alqabas.com":
                    article_id = alqabas_article_id(source_url)
                    if not article_id:
                        errors.append(f"{source_url} -> missing alqabas id")
                        continue
                    parsed = extract_alqabas_api_article(article_id, client)
                    api_fetches += 1
                else:
                    response = client.get(source_url)
                    if response.status_code >= 400:
                        errors.append(f"{source_url} -> HTTP {response.status_code}")
                        continue
                    parsed = extract_article_content(response.content, url=source_url)

                    # JS cookie walls / empty SSR — browser only where needed.
                    discovery_meta = (article.metadata_ or {}).get("discovery") or {}
                    needs_browser = host in {
                        "alwatan.kuwait.tt",
                        "alwatan.com.kw",
                    } or (
                        isinstance(discovery_meta, dict)
                        and discovery_meta.get("discovery") == "playwright"
                    )
                    if (
                        use_browser_fallback
                        and needs_browser
                        and not body_quality_ok(parsed.get("body"))
                        and not parsed.get("paid_article")
                    ):
                        try:
                            from newsfetcher_connectors.browser import (
                                fetch_rendered_html,
                                playwright_available,
                            )

                            if playwright_available():
                                _status, rendered = fetch_rendered_html(
                                    source_url,
                                    user_agent=client.user_agent,
                                    wait_ms=3500,
                                )
                                parsed = extract_article_content(
                                    rendered.encode("utf-8", errors="ignore"),
                                    url=source_url,
                                )
                                browser_fetches += 1
                        except Exception as browser_exc:  # noqa: BLE001
                            errors.append(f"{source_url} -> browser:{browser_exc}")

                published_at = parsed.get("published_at") or article.published_at
                if cutoff is not None and published_at is not None and published_at < cutoff:
                    article.metadata_ = {
                        **(article.metadata_ or {}),
                        "stale_outside_lookback": True,
                        "parsed_published_at": published_at.isoformat(),
                    }
                    # Stamp fetched_at so stale empties are not reselected forever.
                    article.fetched_at = datetime.now(UTC)
                    article.published_at = published_at
                    stale_dropped += 1
                    since_commit += 1
                    if since_commit >= commit_every:
                        db.commit()
                        since_commit = 0
                    continue

                body = parsed.get("body") or ""
                if is_junk_body(body):
                    body = ""

                if not _should_replace_body(article.body_original, body):
                    skipped_overwrite += 1
                    continue

                title = parsed.get("title") or article.title
                if title and len(title) > 1024:
                    title = title[:1023].rstrip() + "…"
                content_hash = hashlib.sha256(
                    f"{title or ''}\n{body}".encode("utf-8", errors="ignore")
                ).hexdigest()
                article.title = title
                article.body_original = body or None
                article.body_normalized = normalize_text(body) if body else None
                article.published_at = published_at
                article.content_hash = content_hash
                article.fetched_at = datetime.now(UTC)
                meta = {**(article.metadata_ or {})}
                meta.pop("stale_outside_lookback", None)
                if published_at is None:
                    meta["date_unknown"] = True
                else:
                    meta.pop("date_unknown", None)
                meta["fetch"] = {
                    "char_count": len(body),
                    "ok": body_quality_ok(body),
                    "body_source": parsed.get("body_source"),
                    "used_next_data": parsed.get("used_next_data"),
                    "browser_fallback": bool(
                        parsed.get("body_source") == "dom" and browser_fetches
                    ),
                    "api_fallback": parsed.get("body_source") == "alqabas_api",
                    "paid_article": bool(parsed.get("paid_article")),
                    "date_unknown": published_at is None,
                }
                article.metadata_ = meta
                image_url = parsed.get("image_url")
                if image_url:
                    image_url = urljoin(source_url, str(image_url).strip())[:2048]
                    image_parts = urlparse(image_url)
                    if image_parts.scheme not in {"http", "https"} or not image_parts.netloc:
                        image_url = None
                if image_url and not db.scalar(
                    select(ArticleImage.id).where(
                        ArticleImage.article_id == article.id,
                        ArticleImage.source_url == image_url,
                    )
                ):
                    db.add(
                        ArticleImage(
                            article_id=article.id,
                            source_url=image_url,
                            metadata_={"role": "cover", "origin": "publisher"},
                        )
                    )
                max_ver = db.scalar(
                    select(func.max(ArticleVersion.version_number)).where(
                        ArticleVersion.article_id == article.id
                    )
                )
                next_ver = int(max_ver or 0) + 1
                if next_ver == 1 or body:
                    db.add(
                        ArticleVersion(
                            article_id=article.id,
                            version_number=next_ver,
                            title=title,
                            body_original=body or None,
                            content_hash=content_hash,
                            raw_snapshot={
                                "source_url": source_url,
                                "fetched": True,
                                "body_source": parsed.get("body_source"),
                            },
                        )
                    )
                fetched += 1
                since_commit += 1
                if since_commit >= commit_every:
                    db.commit()
                    since_commit = 0
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{article.source_url} -> {exc}")
        db.commit()
    finally:
        client.close()

    return {
        "candidates": len(articles),
        "fetched": fetched,
        "stale_dropped": stale_dropped,
        "browser_fetches": browser_fetches,
        "api_fetches": api_fetches,
        "skipped_overwrite": skipped_overwrite,
        "errors": errors[:30],
        "error_count": len(errors),
    }


def backfill_article_images(
    db: Session,
    *,
    limit: int = 300,
    politeness_delay_ms: int = 250,
) -> dict[str, Any]:
    """Populate publisher-provided cover URLs for previously fetched articles."""
    has_image = select(ArticleImage.id).where(ArticleImage.article_id == Article.id).exists()
    articles = list(
        db.scalars(
            select(Article)
            .where(~has_image)
            .order_by(Article.published_at.desc().nulls_last(), Article.discovered_at.desc())
            .limit(limit)
        ).all()
    )
    client = PoliteHttpClient(
        user_agent=(
            "NewsFetcherBot/0.1 (+https://newsfetcher.local; media-monitoring; "
            "contact=ops@newsfetcher.local)"
        ),
        politeness_delay_ms=politeness_delay_ms,
        max_requests_per_minute=90,
        timeout_seconds=20.0,
        transport_fallback="urllib",
    )
    added = 0
    errors: list[str] = []
    try:
        for article in articles:
            try:
                source_url = unescape(article.source_url or "")
                host = urlparse(source_url).netloc.lower().removeprefix("www.")
                if host == "alqabas.com":
                    article_id = alqabas_article_id(source_url)
                    if not article_id:
                        continue
                    parsed = extract_alqabas_api_article(article_id, client)
                else:
                    response = client.get(source_url)
                    if response.status_code >= 400:
                        continue
                    parsed = extract_article_content(response.content, url=source_url)
                image_url = parsed.get("image_url")
                if not image_url:
                    continue
                image_url = urljoin(source_url, str(image_url).strip())[:2048]
                image_parts = urlparse(image_url)
                if image_parts.scheme not in {"http", "https"} or not image_parts.netloc:
                    continue
                db.add(
                    ArticleImage(
                        article_id=article.id,
                        source_url=image_url,
                        metadata_={"role": "cover", "origin": "publisher", "backfilled": True},
                    )
                )
                added += 1
                if added % 20 == 0:
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{article.source_url} -> {exc}")
        db.commit()
    finally:
        client.close()
    return {
        "candidates": len(articles),
        "added": added,
        "error_count": len(errors),
        "errors": errors[:20],
    }


def backfill_missing_dates(
    db: Session,
    *,
    lookback_days: int | None = 5,
    limit: int = 200,
    politeness_delay_ms: int = 300,
    use_browser_for_hosts: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Fill published_at for undated articles; mark stale / date_unknown accordingly."""
    browser_hosts = use_browser_for_hosts or frozenset(
        {"alwatan.kuwait.tt", "alwatan.com.kw"}
    )
    stmt = (
        select(Article)
        .where(Article.published_at.is_(None))
        .order_by(Article.discovered_at.desc())
        .limit(limit)
    )
    articles = list(db.scalars(stmt).all())
    client = PoliteHttpClient(
        user_agent=(
            "NewsFetcherBot/0.1 (+https://newsfetcher.local; media-monitoring; "
            "contact=ops@newsfetcher.local)"
        ),
        politeness_delay_ms=politeness_delay_ms,
        max_requests_per_minute=60,
        timeout_seconds=25.0,
        transport_fallback="urllib",
    )
    updated = 0
    stale = 0
    still_unknown = 0
    errors: list[str] = []
    cutoff = None
    if lookback_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    try:
        for article in articles:
            try:
                source_url = unescape(article.source_url or "")
                host = urlparse(source_url).netloc.lower().removeprefix("www.")
                html_bytes: bytes | None = None

                if host == "alqabas.com":
                    article_id = alqabas_article_id(source_url)
                    if not article_id:
                        still_unknown += 1
                        continue
                    parsed = extract_alqabas_api_article(article_id, client)
                else:
                    # Prefer static HTML first; browser only when date still missing.
                    response = client.get(source_url)
                    if response.status_code >= 400:
                        errors.append(f"{source_url} -> HTTP {response.status_code}")
                        still_unknown += 1
                        continue
                    html_bytes = response.content
                    parsed = extract_article_content(html_bytes, url=source_url)
                    if parsed.get("published_at") is None and host in browser_hosts:
                        try:
                            from newsfetcher_connectors.browser import (
                                fetch_rendered_html,
                                playwright_available,
                            )

                            if playwright_available():
                                _status, rendered = fetch_rendered_html(
                                    source_url,
                                    user_agent=client.user_agent,
                                    wait_ms=3500,
                                )
                                html_bytes = rendered.encode("utf-8", errors="ignore")
                                parsed = extract_article_content(
                                    html_bytes, url=source_url
                                )
                        except Exception as browser_exc:  # noqa: BLE001
                            errors.append(f"{source_url} -> browser:{browser_exc}")

                published_at = parsed.get("published_at")
                meta = {**(article.metadata_ or {})}
                if published_at is None:
                    meta["date_unknown"] = True
                    article.metadata_ = meta
                    still_unknown += 1
                    continue

                article.published_at = published_at
                meta.pop("date_unknown", None)
                if cutoff is not None and published_at < cutoff:
                    meta["stale_outside_lookback"] = True
                    meta["parsed_published_at"] = published_at.isoformat()
                    stale += 1
                else:
                    meta.pop("stale_outside_lookback", None)
                meta["date_backfill"] = {
                    "published_at": published_at.isoformat(),
                    "source": parsed.get("body_source") or "page_date",
                }
                article.metadata_ = meta
                updated += 1
                if updated % 20 == 0:
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{article.source_url} -> {exc}")
                still_unknown += 1
        db.commit()
    finally:
        client.close()

    return {
        "candidates": len(articles),
        "updated": updated,
        "stale_marked": stale,
        "still_unknown": still_unknown,
        "errors": errors[:30],
        "error_count": len(errors),
    }
