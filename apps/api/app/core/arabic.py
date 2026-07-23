"""Arabic/English normalization for alias storage (matching Phase 4 will reuse this)."""

from __future__ import annotations

import re
import unicodedata

_TATWEEL = "\u0640"
_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_ALEF_RE = re.compile(r"[إأآٱ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.replace(_TATWEEL, "")
    text = _DIACRITICS_RE.sub("", text)
    text = _ALEF_RE.sub("ا", text)
    text = text.translate(_DIGITS)
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text
