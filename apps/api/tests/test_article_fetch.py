from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.services.article_fetch import (
    body_quality_ok,
    extract_alqabas_api_article,
    extract_article_content,
    is_junk_body,
)
from app.services.ingestion import normalize_url


def test_extract_article_content_reads_title_body_and_date() -> None:
    html = b"""
    <html><head>
      <meta property="og:title" content="Demo Headline" />
      <meta property="article:published_time" content="2026-07-20T10:00:00Z" />
    </head><body>
      <article>
        <h1>Demo Headline</h1>
        <p>This is a sufficiently long paragraph used to verify body extraction works well.</p>
        <p>Second paragraph with more text so the extractor keeps meaningful content only.</p>
      </article>
    </body></html>
    """
    parsed = extract_article_content(html, url="https://example.test/news/2026/07/20/demo")
    assert parsed["title"] == "Demo Headline"
    assert parsed["published_at"] is not None
    assert parsed["published_at"].year == 2026
    assert "sufficiently long paragraph" in parsed["body"]


def test_extract_article_content_reads_square_card_cover() -> None:
    html = b"""
    <html><head>
      <meta property="og:title" content="Image story" />
      <meta property="og:image" content="/media/story-cover.jpg" />
    </head><body>
      <article>
        <p>This is a sufficiently long article body for validating the publisher cover image.</p>
        <p>The second paragraph ensures this is accepted as meaningful article content.</p>
      </article>
    </body></html>
    """
    parsed = extract_article_content(html, url="https://publisher.test/news/story")
    assert parsed["image_url"] == "https://publisher.test/media/story-cover.jpg"


def test_extract_prefers_json_ld_article_body_over_sidebar_dom() -> None:
    body = "أظهرت بيانات الهيئة العامة للمعلومات المدنية أن اسم محمد جاء في صدارة الأسماء " * 3
    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "محمد وفاطمة",
        "datePublished": "2026-07-22T22:01:00+03:00",
        "articleBody": body,
    }
    html = f"""
    <html><head>
      <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
    </head><body>
      <aside><p>مواسم الصيد الحالية ستنعش السوق والأسعار ستتراجع منذ 7 دقائق</p></aside>
      <div class="article-desc"><p>short teaser only here for the page</p></div>
    </body></html>
    """.encode()
    parsed = extract_article_content(html, url="https://www.alraimedia.com/article/1/x")
    assert parsed["title"] == "محمد وفاطمة"
    assert parsed["body_source"] == "json_ld"
    assert body.strip() == parsed["body"].strip()
    assert "مواسم الصيد" not in parsed["body"]


def test_extract_reads_cms_article_info_script_with_kuwait_tz() -> None:
    info = {
        "article_title": "عنوان السياسة",
        "publish_time": "2026-07-22 21:35:00",
        "article_body": (
            "<p>استقبلت المحكمة الكلية 25 ألفاً و895 قضية جديدة خلال شهر مايو 2026 "
            "بواقع قضايا جزائية وغير جزائية مع نسب إنجاز مرتفعة في الإعلانات.</p>"
        ),
    }
    html = f"""
    <html><body>
      <div class="article">{{{{ article.article_title }}}}</div>
      <script>var article_info = {json.dumps(info, ensure_ascii=False)};</script>
    </body></html>
    """.encode()
    parsed = extract_article_content(html, url="https://alseyassah.com/article/1/x")
    assert parsed["title"] == "عنوان السياسة"
    assert parsed["body_source"] == "article_info"
    assert "المحكمة الكلية" in parsed["body"]
    assert parsed["char_count"] > 80
    # Naive CMS time is Asia/Kuwait (+03) → 18:35 UTC
    assert parsed["published_at"] == datetime(2026, 7, 22, 18, 35, tzinfo=UTC)


def test_rejects_alqabas_nav_menu_as_body() -> None:
    html = """
    <html><body>
      <nav>
        <p>عدد اليوم</p><p>ماستر كلاس</p><p>وفيات</p><p>معرض الصور</p>
        <p>كتاب القبس</p><p>أرشيف القبس</p><p>بودكاست</p>
      </nav>
    </body></html>
    """.encode()
    parsed = extract_article_content(html, url="https://www.alqabas.com/article/1/x")
    assert parsed["body"] == ""
    assert is_junk_body(
        "عدد اليوم\nماستر كلاس\nوفيات\nمعرض الصور\nكتاب القبس\nأرشيف القبس\nبودكاست"
    )
    assert not body_quality_ok(
        "عدد اليوم\nماستر كلاس\nوفيات\nمعرض الصور\nكتاب القبس\nأرشيف القبس\nبودكاست"
    )


def test_extract_alqabas_api_article() -> None:
    payload = {
        "data": {
            "result": {
                "title": "عنوان القبس",
                "content": "<p>" + ("نص المقال الحقيقي هنا. " * 20) + "</p>",
                "publishDate": "2026-07-22T19:03:32.060Z",
                "paidArticle": False,
            }
        }
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    client = MagicMock()
    client.get.return_value = response
    parsed = extract_alqabas_api_article("5967707", client)
    assert parsed["title"] == "عنوان القبس"
    assert parsed["body_source"] == "alqabas_api"
    assert "نص المقال الحقيقي" in parsed["body"]
    assert parsed["published_at"] is not None
    assert parsed["published_at"].year == 2026
    client.get.assert_called_once()


def test_extract_reads_wasat_lbl_date() -> None:
    html = """
    <html><body>
      <span id="ctl00_ContentPlaceHolder1_lblDate" class="small">22/07/2026 09:28</span>
      <article><p>
        هذا نص مقال طويل بما يكفي لاعتباره محتوى صالحاً للتخزين في النظام هنا.
      </p></article>
    </body></html>
    """.encode()
    parsed = extract_article_content(html, url="https://www.alwasat.com.kw/ArticleDetail.aspx?id=1")
    assert parsed["published_at"] is not None
    assert parsed["published_at"].day == 22
    assert parsed["published_at"].month == 7
    assert parsed["published_at"].year == 2026
    assert parsed["published_at"].hour == 9
    assert parsed["date_unknown"] is False


def test_extract_reads_watan_writer_link_date() -> None:
    html = """
    <html><body>
      <span id="ctl00_lblGrogerianDate">23/07/2026 م</span>
      <font class="WriterLink"></font>
      <font class="WriterLink">2026/07/20</font>
      <font class="WriterLink">05:10 م</font>
      <div class="article-body"><p>
        محتوى الوطن بعد تجاوز جدار الكوكيز يجب أن يُستخرج كتاريخ نشر صحيح للمقال.
      </p></div>
    </body></html>
    """.encode()
    parsed = extract_article_content(
        html, url="https://alwatan.kuwait.tt/articledetails.aspx?id=829529"
    )
    assert parsed["published_at"] is not None
    assert parsed["published_at"].date().isoformat() == "2026-07-20"
    assert parsed["published_at"].hour == 17  # 05:10 PM
    assert parsed["date_unknown"] is False


def test_normalize_url_unescapes_amp_and_keeps_id() -> None:
    assert (
        normalize_url(
            "https://alwatan.kuwait.tt/articledetails.aspx?id=467771&amp;yearquarter=20161"
        )
        == "https://alwatan.kuwait.tt/articledetails.aspx?id=467771"
    )
    assert (
        normalize_url(
            "HTTPS://www.KUNA.net.kw/ArticleDetails.aspx?id=1&Language=AR&yearquarter=20161"
        )
        == "https://www.kuna.net.kw/ArticleDetails.aspx?id=1&language=ar"
    )
