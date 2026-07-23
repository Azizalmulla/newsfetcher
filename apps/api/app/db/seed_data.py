"""Mandatory Kuwait source inventory for Phase 0.

No live fetching is performed. All assessments start as pending_assessment.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ChannelSeed(TypedDict):
    code: str
    label: str
    language: str
    base_url: str


class PublisherSeed(TypedDict):
    code: str
    name_en: str
    name_ar: str
    homepage_url: str
    media_type: str
    channels: list[ChannelSeed]


MANDATORY_PUBLISHERS: list[PublisherSeed] = [
    {
        "code": "alanba",
        "name_en": "Al-Anbaa",
        "name_ar": "الأنباء",
        "homepage_url": "https://www.alanba.com.kw",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al-Anbaa Arabic Web",
                "language": "ar",
                "base_url": "https://www.alanba.com.kw",
            },
            {
                "code": "epaper_ar",
                "label": "Al-Anbaa Arabic E-paper",
                "language": "ar",
                "base_url": "https://www.alanba.com.kw",
            },
        ],
    },
    {
        "code": "alqabas",
        "name_en": "Al Qabas",
        "name_ar": "القبس",
        "homepage_url": "https://alqabas.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Qabas Arabic Web",
                "language": "ar",
                "base_url": "https://alqabas.com",
            }
        ],
    },
    {
        "code": "alrai",
        "name_en": "Al Rai",
        "name_ar": "الراي",
        "homepage_url": "https://www.alraimedia.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Rai Arabic Web",
                "language": "ar",
                "base_url": "https://www.alraimedia.com",
            }
        ],
    },
    {
        "code": "aljarida",
        "name_en": "Al Jarida",
        "name_ar": "الجريدة",
        "homepage_url": "https://www.aljarida.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Jarida Arabic Web",
                "language": "ar",
                "base_url": "https://www.aljarida.com",
            }
        ],
    },
    {
        "code": "alseyassah",
        "name_en": "Al Seyassah",
        "name_ar": "السياسة",
        # Live hostname is alseyassah.com; al-seyassah.com currently serves a dead index.
        "homepage_url": "https://alseyassah.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Seyassah Arabic Web",
                "language": "ar",
                "base_url": "https://alseyassah.com",
            }
        ],
    },
    {
        "code": "kuwaittimes",
        "name_en": "Kuwait Times",
        "name_ar": "كويت تايمز",
        "homepage_url": "https://kuwaittimes.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_en",
                "label": "Kuwait Times English Web",
                "language": "en",
                "base_url": "https://kuwaittimes.com",
            }
        ],
    },
    {
        "code": "arabtimes",
        "name_en": "Arab Times",
        "name_ar": "عرب تايمز",
        "homepage_url": "https://www.arabtimesonline.com",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_en",
                "label": "Arab Times English Web",
                "language": "en",
                "base_url": "https://www.arabtimesonline.com",
            }
        ],
    },
    {
        "code": "kuna",
        "name_en": "KUNA",
        "name_ar": "وكالة الأنباء الكويتية",
        "homepage_url": "https://www.kuna.net.kw",
        "media_type": "agency",
        "channels": [
            {
                "code": "web_ar",
                "label": "KUNA Arabic",
                "language": "ar",
                "base_url": "https://www.kuna.net.kw",
            },
            {
                "code": "web_en",
                "label": "KUNA English",
                "language": "en",
                "base_url": "https://www.kuna.net.kw/ArticleSearchPage.aspx?language=en",
            },
        ],
    },
    {
        "code": "alwasat",
        "name_en": "Al Wasat",
        "name_ar": "الوسط",
        "homepage_url": "https://www.alwasat.com.kw",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Wasat Arabic Web",
                "language": "ar",
                "base_url": "https://www.alwasat.com.kw",
            }
        ],
    },
    {
        "code": "alwatan",
        "name_en": "Al Watan",
        "name_ar": "الوطن",
        "homepage_url": "https://alwatan.kuwait.tt",
        "media_type": "newspaper",
        "channels": [
            {
                "code": "web_ar",
                "label": "Al Watan Arabic Web",
                "language": "ar",
                "base_url": "https://alwatan.kuwait.tt",
            }
        ],
    },
]

INITIAL_ROLES: list[dict[str, str]] = [
    {
        "code": "platform_admin",
        "name": "Platform Admin",
        "description": "Platform-wide administration",
    },
    {
        "code": "tenant_admin",
        "name": "Tenant Admin",
        "description": "Tenant workspace administration",
    },
    {
        "code": "editor_reviewer",
        "name": "Editor/Reviewer",
        "description": "Review matches and prepare reports",
    },
    {
        "code": "viewer",
        "name": "Viewer",
        "description": "Read-only access to tenant workspace",
    },
]


def expected_channel_count() -> int:
    return sum(len(publisher["channels"]) for publisher in MANDATORY_PUBLISHERS)


def inventory_summary() -> dict[str, Any]:
    return {
        "publisher_count": len(MANDATORY_PUBLISHERS),
        "channel_count": expected_channel_count(),
        "kuna_channels": [
            channel["code"]
            for publisher in MANDATORY_PUBLISHERS
            if publisher["code"] == "kuna"
            for channel in publisher["channels"]
        ],
    }
