from app.services.embeddings import LocalHashEmbeddingProvider, cosine_similarity


def test_local_embeddings_are_deterministic_and_normalized() -> None:
    provider = LocalHashEmbeddingProvider(dimensions=64)
    a = provider.embed(["AI Octopus Kuwait automation"])[0]
    b = provider.embed(["AI Octopus Kuwait automation"])[0]
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_similar_texts_rank_higher_than_unrelated() -> None:
    provider = LocalHashEmbeddingProvider(dimensions=256)
    query = provider.embed(["AI Octopus automation Kuwait"], input_type="query")[0]
    related = provider.embed(["AI Octopus wins automation contract in Kuwait"])[0]
    unrelated = provider.embed(["Oil prices rose in the North Sea market"])[0]
    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)
