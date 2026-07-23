"""Guardrails: no Playwright and no paywall-bypass helpers."""

from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]


def test_playwright_only_in_browser_connector_path() -> None:
    """Playwright is allowed for the browser connector; not for general HTML/RSS."""
    browser = (
        REPO_ROOT
        / "packages"
        / "connectors"
        / "newsfetcher_connectors"
        / "browser.py"
    ).read_text(encoding="utf-8")
    html = (
        REPO_ROOT
        / "packages"
        / "connectors"
        / "newsfetcher_connectors"
        / "html.py"
    ).read_text(encoding="utf-8")
    rss = (
        REPO_ROOT / "packages" / "connectors" / "newsfetcher_connectors" / "rss.py"
    ).read_text(encoding="utf-8")
    assert "playwright" in browser.lower()
    assert "playwright" not in html.lower()
    assert "playwright" not in rss.lower()


def test_no_paywall_bypass_helpers() -> None:
    forbidden_tokens = ["bypass_paywall", "break_captcha", "steal_cookie"]
    roots = [
        API_ROOT / "app",
        REPO_ROOT / "packages" / "connectors" / "newsfetcher_connectors",
    ]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden_tokens:
                assert token not in text, f"{token} found in {path}"


def test_assessments_never_auto_approve_legal_gate() -> None:
    text = (API_ROOT / "app" / "services" / "source_assessment.py").read_text(encoding="utf-8")
    assert "assessment.legal_gate = LegalGate.pending" in text
    assert "legal_gate = LegalGate.approved" not in text


def test_phase8_closure_never_enables_or_approves() -> None:
    text = (API_ROOT / "app" / "services" / "source_closure.py").read_text(encoding="utf-8")
    assert "connector.enabled = False" in text
    assert "LegalGate.approved" not in text
    assert "enabled = True" not in text


def test_enablement_is_explicit_ops_module() -> None:
    """Live enable lives only in source_enablement, not assessment/closure writers."""
    enablement = (API_ROOT / "app" / "services" / "source_enablement.py").read_text(
        encoding="utf-8"
    )
    assert "LegalGate.approved" in enablement
    assert "connector.enabled = True" in enablement
    assessment = (API_ROOT / "app" / "services" / "source_assessment.py").read_text(
        encoding="utf-8"
    )
    assert "LegalGate.approved" not in assessment


def test_social_module_forbids_html_scrape() -> None:
    social = (API_ROOT / "app" / "services" / "social.py").read_text(encoding="utf-8")
    x_api = (API_ROOT / "app" / "services" / "x_api.py").read_text(encoding="utf-8")
    assert "scrape" in x_api.lower() or "Never scrapes" in x_api
    assert "x.com/i/api" not in social
    assert "nitter" not in social.lower()
    assert "BeautifulSoup" not in x_api
    assert "playwright" not in x_api.lower()
