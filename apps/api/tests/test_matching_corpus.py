from __future__ import annotations

import json
from pathlib import Path

from app.core.arabic import normalize_text
from app.services.matching_engine import MatchTerm, match_document

CORPUS = json.loads(
    (Path(__file__).parent / "fixtures" / "matching_corpus.json").read_text(encoding="utf-8")
)


def _terms_from_entity(entity: dict) -> list[MatchTerm]:
    terms: list[MatchTerm] = []
    if entity.get("canonical_name_en"):
        terms.append(
            MatchTerm(
                surface=entity["canonical_name_en"],
                normalized=normalize_text(entity["canonical_name_en"]),
                language="en",
                source="canonical",
            )
        )
    if entity.get("canonical_name_ar"):
        terms.append(
            MatchTerm(
                surface=entity["canonical_name_ar"],
                normalized=normalize_text(entity["canonical_name_ar"]),
                language="ar",
                source="canonical",
            )
        )
    for alias in entity.get("aliases", []):
        terms.append(
            MatchTerm(
                surface=alias["alias_text"],
                normalized=normalize_text(alias["alias_text"]),
                language=alias["language"],
                source="alias",
            )
        )
    return terms


def test_matching_corpus_precision_recall_fixtures() -> None:
    false_positives = 0
    false_negatives = 0
    for case in CORPUS:
        exclusions = [
            normalize_text(item["phrase"]) for item in case["entity"].get("exclusions", [])
        ]
        result = match_document(
            title=case["title"],
            body=case["body"],
            terms=_terms_from_entity(case["entity"]),
            exclusions_normalized=exclusions,
        )
        expect_match = case["expect_match"]
        if case.get("expect_excluded"):
            assert result is not None and result.excluded, case["id"]
            continue
        if expect_match:
            if result is None or result.excluded:
                false_negatives += 1
                continue
            allowed = set(case.get("expect_types_any", []))
            types = {hit.match_type for hit in result.evidence}
            assert types & allowed, f"{case['id']}: got {types}, expected any of {allowed}"
        else:
            if result is not None and not result.excluded:
                false_positives += 1

    assert false_positives == 0, f"false positives={false_positives}"
    assert false_negatives == 0, f"false negatives={false_negatives}"
