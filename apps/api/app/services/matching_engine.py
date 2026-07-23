"""Deterministic layered matching (Phase 4).

Order:
1. exact
2. case_insensitive_en
3. arabic_normalized
4. alias
5. controlled_fuzzy

Exclusions veto after candidate generation.
No embeddings/LLM in this phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from app.core.arabic import normalize_text

# Controlled fuzzy thresholds — names should not over-stem.
FUZZY_MIN_RATIO = 0.92
FUZZY_MIN_TERM_LEN = 6


@dataclass(frozen=True)
class MatchTerm:
    surface: str
    normalized: str
    language: str
    exact_only: bool = False
    source: str = "canonical"  # canonical|alias


@dataclass
class EvidenceHit:
    match_type: str
    score: float
    surface_form: str
    normalized_form: str
    field_name: str
    start_offset: int | None
    end_offset: int | None
    evidence_span: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchCandidate:
    matched_term: str
    matched_term_normalized: str
    best_match_type: str
    best_score: float
    snippet: str
    evidence: list[EvidenceHit] = field(default_factory=list)
    excluded: bool = False
    exclusion_phrase: str | None = None


def _window(text: str, start: int, end: int, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].strip()
    if left > 0:
        snippet = "…" + snippet
    if right < len(text):
        snippet = snippet + "…"
    return snippet


def _find_exact(haystack: str, needle: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            break
        spans.append((idx, idx + len(needle)))
        start = idx + max(len(needle), 1)
    return spans


def _normalized_contains(
    original: str, needle_normalized: str
) -> list[tuple[int | None, int | None, str]]:
    """Return hit markers when normalized needle appears in normalized original.

    Uses linear scan over whitespace tokens (O(n)), not character windows.
    """
    if not needle_normalized:
        return []
    original_norm = normalize_text(original)
    if needle_normalized not in original_norm:
        return []

    # Try recovering a surface span via token-window equality on normalized tokens.
    needle_tokens = needle_normalized.split()
    if not needle_tokens:
        return [(None, None, needle_normalized)]

    # Map original tokens to normalized forms with offsets.
    tokens: list[tuple[str, int, int]] = []
    i = 0
    while i < len(original):
        while i < len(original) and original[i].isspace():
            i += 1
        if i >= len(original):
            break
        j = i
        while j < len(original) and not original[j].isspace():
            j += 1
        token = original[i:j]
        tokens.append((token, i, j))
        i = j

    n = len(needle_tokens)
    hits: list[tuple[int | None, int | None, str]] = []
    for idx in range(0, max(0, len(tokens) - n + 1)):
        window = tokens[idx : idx + n]
        window_norm = normalize_text(" ".join(tok for tok, _, _ in window))
        if window_norm == needle_normalized:
            start = window[0][1]
            end = window[-1][2]
            hits.append((start, end, original[start:end]))
    if hits:
        return hits
    return [(None, None, needle_normalized)]


def _fuzzy_hits(haystack_norm: str, needle_norm: str) -> list[tuple[float, str]]:
    if len(needle_norm) < FUZZY_MIN_TERM_LEN:
        return []
    tokens = haystack_norm.split()
    if not tokens:
        return []
    n_words = max(1, len(needle_norm.split()))
    hits: list[tuple[float, str]] = []
    for i in range(len(tokens)):
        for width in (n_words, n_words + 1):
            gram = " ".join(tokens[i : i + width])
            if not gram or gram == needle_norm:
                continue
            ratio = SequenceMatcher(None, gram, needle_norm).ratio()
            if ratio >= FUZZY_MIN_RATIO:
                hits.append((ratio, gram))
    hits.sort(key=lambda item: item[0], reverse=True)
    return hits[:3]


def match_document(
    *,
    title: str | None,
    body: str | None,
    terms: list[MatchTerm],
    exclusions_normalized: list[str],
) -> MatchCandidate | None:
    fields = {
        "title": title or "",
        "body": body or "",
    }
    combined_original = "\n".join(part for part in (title or "", body or "") if part)
    combined_normalized = normalize_text(combined_original)

    for phrase in exclusions_normalized:
        if phrase and phrase in combined_normalized:
            return MatchCandidate(
                matched_term="",
                matched_term_normalized="",
                best_match_type="excluded",
                best_score=0.0,
                snippet="",
                evidence=[],
                excluded=True,
                exclusion_phrase=phrase,
            )

    evidence: list[EvidenceHit] = []
    seen_keys: set[tuple[str, str, int | None, int | None]] = set()

    def _add(hit: EvidenceHit) -> None:
        key = (hit.match_type, hit.field_name, hit.start_offset, hit.end_offset)
        if key in seen_keys:
            return
        seen_keys.add(key)
        evidence.append(hit)

    for field_name, original in fields.items():
        if not original:
            continue
        lowered = original.lower()
        normalized_field = normalize_text(original)

        for term in terms:
            # 1) Exact
            for start, end in _find_exact(original, term.surface):
                _add(
                    EvidenceHit(
                        match_type="exact",
                        score=1.0,
                        surface_form=original[start:end],
                        normalized_form=normalize_text(term.surface),
                        field_name=field_name,
                        start_offset=start,
                        end_offset=end,
                        evidence_span=_window(original, start, end),
                        details={"term_source": term.source},
                    )
                )

            # 2) Case-insensitive English
            if term.language == "en" or any(ch.isascii() and ch.isalpha() for ch in term.surface):
                for start, end in _find_exact(lowered, term.surface.lower()):
                    surface = original[start:end]
                    if surface == term.surface:
                        continue
                    _add(
                        EvidenceHit(
                            match_type="case_insensitive_en",
                            score=0.99,
                            surface_form=surface,
                            normalized_form=term.normalized,
                            field_name=field_name,
                            start_offset=start,
                            end_offset=end,
                            evidence_span=_window(original, start, end),
                            details={"term_source": term.source},
                        )
                    )

            # 3/4) Arabic-normalized / alias-normalized
            match_type = "alias" if term.source == "alias" else "arabic_normalized"
            for norm_start, norm_end, surface in _normalized_contains(
                original, term.normalized
            ):
                score = 0.97 if match_type == "arabic_normalized" else 0.96
                if norm_start is not None and norm_end is not None:
                    _add(
                        EvidenceHit(
                            match_type=match_type,
                            score=score,
                            surface_form=surface,
                            normalized_form=term.normalized,
                            field_name=field_name,
                            start_offset=norm_start,
                            end_offset=norm_end,
                            evidence_span=_window(original, norm_start, norm_end),
                            details={"term_source": term.source},
                        )
                    )
                else:
                    _add(
                        EvidenceHit(
                            match_type=match_type,
                            score=score,
                            surface_form=surface,
                            normalized_form=term.normalized,
                            field_name=field_name,
                            start_offset=None,
                            end_offset=None,
                            evidence_span=surface,
                            details={
                                "term_source": term.source,
                                "offset_quality": "approximate",
                            },
                        )
                    )

            # 5) Controlled fuzzy
            if term.exact_only:
                continue
            for ratio, gram in _fuzzy_hits(normalized_field, term.normalized):
                _add(
                    EvidenceHit(
                        match_type="controlled_fuzzy",
                        score=round(ratio, 4),
                        surface_form=gram,
                        normalized_form=term.normalized,
                        field_name=field_name,
                        start_offset=None,
                        end_offset=None,
                        evidence_span=gram,
                        details={"term_source": term.source, "fuzzy_ratio": ratio},
                    )
                )

    if not evidence:
        return None

    rank = {
        "exact": 5,
        "case_insensitive_en": 4,
        "arabic_normalized": 3,
        "alias": 3,
        "controlled_fuzzy": 1,
    }
    evidence.sort(key=lambda hit: (rank.get(hit.match_type, 0), hit.score), reverse=True)
    best = evidence[0]
    return MatchCandidate(
        matched_term=best.surface_form,
        matched_term_normalized=best.normalized_form,
        best_match_type=best.match_type,
        best_score=best.score,
        snippet=best.evidence_span,
        evidence=evidence[:10],
    )
