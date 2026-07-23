from app.services.relevance import classify_relevance


def test_strong_lexical_is_relevant() -> None:
    result = classify_relevance(
        vector_similarity=0.5,
        rerank_score=0.4,
        lexical_best_score=1.0,
    )
    assert result.label == "relevant"
    assert result.confidence >= 0.85


def test_weak_signals_not_relevant() -> None:
    result = classify_relevance(
        vector_similarity=0.1,
        rerank_score=0.05,
        lexical_best_score=0.0,
    )
    assert result.label == "not_relevant"


def test_ambiguous_needs_review() -> None:
    result = classify_relevance(
        vector_similarity=0.6,
        rerank_score=0.4,
        lexical_best_score=0.3,
    )
    assert result.label == "needs_review"
