import enum


class SourceAssessmentStatus(enum.StrEnum):
    pending_assessment = "pending_assessment"
    approved_for_rss = "approved_for_rss"
    approved_for_public_api = "approved_for_public_api"
    approved_for_html_fetch = "approved_for_html_fetch"
    requires_browser = "requires_browser"
    requires_license = "requires_license"
    blocked_by_paywall = "blocked_by_paywall"
    temporarily_broken = "temporarily_broken"
    active = "active"
    disabled = "disabled"


class ConnectorMethod(enum.StrEnum):
    licensed_api = "licensed_api"
    rss = "rss"
    sitemap = "sitemap"
    html = "html"
    browser = "browser"
    epaper = "epaper"
    blocked = "blocked"
    pending = "pending"


class LegalGate(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    blocked = "blocked"


class JobRunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead_letter = "dead_letter"
    cancelled = "cancelled"


class ChannelLanguage(enum.StrEnum):
    ar = "ar"
    en = "en"
