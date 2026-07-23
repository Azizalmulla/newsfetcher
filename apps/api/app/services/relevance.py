"""Rule-based relevance classifier (Phase 5).

Does not invent citations. Combines lexical + vector + rerank signals.
Ambiguous cases escalate to review; never auto-final.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RelevanceResult:
    label: str  # relevant|not_relevant|needs_review
    confidence: float
    reason: str
    features: dict[str, Any]
    schema_version: str = "v1"
    prompt_version: str = "rules_v1"


def classify_relevance(
    *,
    vector_similarity: float,
    rerank_score: float | None,
    lexical_best_score: float,
    min_classifier: float = 0.6,
) -> RelevanceResult:
    rerank = rerank_score if rerank_score is not None else 0.0
    # Weighted feature score; lexical evidence strongly boosts confidence.
    score = (
        (0.35 * vector_similarity)
        + (0.25 * rerank)
        + (0.40 * min(lexical_best_score, 1.0))
    )
    features = {
        "vector_similarity": vector_similarity,
        "rerank_score": rerank_score,
        "lexical_best_score": lexical_best_score,
        "weighted_score": score,
    }

    if lexical_best_score >= 0.96 and vector_similarity >= 0.4:
        return RelevanceResult(
            label="relevant",
            confidence=min(0.99, 0.85 + 0.1 * lexical_best_score),
            reason="Strong deterministic lexical evidence with supporting semantic similarity.",
            features=features,
        )
    if score >= max(min_classifier, 0.75) and lexical_best_score >= 0.5:
        return RelevanceResult(
            label="relevant",
            confidence=score,
            reason="Combined lexical and semantic scores exceed relevance threshold.",
            features=features,
        )
    if score < 0.35 and lexical_best_score < 0.2:
        return RelevanceResult(
            label="not_relevant",
            confidence=1.0 - score,
            reason="Weak lexical and semantic signals.",
            features=features,
        )
    return RelevanceResult(
        label="needs_review",
        confidence=score,
        reason="Ambiguous relevance; escalate to human review.",
        features=features,
    )
