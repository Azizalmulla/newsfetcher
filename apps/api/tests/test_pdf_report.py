from __future__ import annotations

from app.services.pdf_report import render_press_clipping_pdf


def test_render_press_clipping_pdf_produces_valid_pdf() -> None:
    pdf = render_press_clipping_pdf(
        {
            "title": "Daily Kuwait Clips",
            "tenant_name": "Demo Tenant",
            "period_start": "2026-07-20",
            "period_end": "2026-07-21",
            "version_number": 1,
            "content_hash": "abc123",
            "notes": "Client-ready pack",
            "branding": {
                "display_name": "Demo Tenant",
                "primary_color": "#0B3D2E",
                "accent_color": "#C4A35A",
                "footer_text": "Confidential",
            },
            "items": [
                {
                    "included": True,
                    "title_snapshot": "AI Octopus expands",
                    "source_name_snapshot": "Al-Anbaa",
                    "url_snapshot": "https://example.test/a",
                    "snippet_snapshot": "Mention in Kuwait City.",
                    "note": "Front page",
                }
            ],
        }
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500
