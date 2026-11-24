
import re
import time

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from .storage import get_vectorstore, get_all_chunks
from .config import RERANKER_MODEL


_reranker = None


def _tokens(text):
    return re.findall(r"[a-zA-Z0-9_./:-]+", text.lower())


def _get_reranker():
    global _reranker

    if _reranker is None:
        _reranker = CrossEncoder(
            RERANKER_MODEL,
            max_length=512
        )

    return _reranker


def _format_result(doc, score, rerank_score=None):
    return {
        "text": doc.page_content,
        "source": doc.metadata.get("source", "unknown"),
        "chunk_id": doc.metadata.get("chunk_id", ""),
        "score": round(float(score), 6),
        "rerank_score": (
            round(float(rerank_score), 6)
            if rerank_score is not None else None
        )
    }


# --------------------------------------------------
# 1. VECTOR SEARCH
# --------------------------------------------------

def vector_search(query, top_k=8):

    results = get_vectorstore().similarity_search_with_relevance_scores(
        query,
        k=top_k
    )

    return [
        _format_result(doc, score)
        for doc, score in results
    ]


# --------------------------------------------------
# 2. BM25 SEARCH
# --------------------------------------------------

def bm25_search(query, top_k=8):

    chunks = get_all_chunks()

    if not chunks:
        return []

    corpus = [
        _tokens(item["text"])
        for item in chunks
    ]

    bm25 = BM25Okapi(corpus)

    scores = bm25.get_scores(_tokens(query))

    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True
    )[:top_k]

    results = []

    for index, score in ranked:

        item = chunks[index]

        doc = Document(
            page_content=item["text"],
            metadata=item["metadata"]
        )

        results.append(
            _format_result(doc, score)
        )

    return results


# --------------------------------------------------
# 3. RECIPROCAL RANK FUSION
# --------------------------------------------------

def reciprocal_rank_fusion(
    vector_results,
    lexical_results,
    top_k=8
):

    combined = {}

    for rank, item in enumerate(vector_results, start=1):

        key = item["chunk_id"] or item["text"][:80]

        combined[key] = {
            "item": item,
            "rrf": 0.55 / (60 + rank)
        }

    for rank, item in enumerate(lexical_results, start=1):

        key = item["chunk_id"] or item["text"][:80]

        if key not in combined:

            combined[key] = {
                "item": item,
                "rrf": 0
            }

        combined[key]["rrf"] += 0.45 / (60 + rank)

    ranked = sorted(
        combined.values(),
        key=lambda item: item["rrf"],
        reverse=True
    )

    return ranked[:max(top_k * 2, top_k)]


# --------------------------------------------------
# 4. CROSS-ENCODER RERANKING
# --------------------------------------------------

def rerank_results(query, candidates):

    if not candidates:
        return []

    reranker = _get_reranker()

    pairs = [
        (query, item["item"]["text"])
        for item in candidates
    ]

    scores = reranker.predict(pairs)

    for item, score in zip(candidates, scores):

        item["rerank_score"] = float(score)

    candidates.sort(
        key=lambda item: item["rerank_score"],
        reverse=True
    )

    return candidates


# --------------------------------------------------
# 5. MAIN RETRIEVAL FUNCTION
# --------------------------------------------------

def search(
    query,
    top_k=8,
    retrieval_mode="hybrid",
    use_reranker=True
):

    start_time = time.perf_counter()

    if retrieval_mode == "vector":

        results = vector_search(query, top_k)

    elif retrieval_mode == "bm25":

        results = bm25_search(query, top_k)

    elif retrieval_mode == "hybrid":

        vector_results = vector_search(
            query,
            top_k * 2
        )

        lexical_results = bm25_search(
            query,
            top_k * 2
        )

        candidates = reciprocal_rank_fusion(
            vector_results,
            lexical_results,
            top_k
        )

        if use_reranker and candidates:

            try:

                candidates = rerank_results(
                    query,
                    candidates
                )

            except Exception as exc:

                print(
                    "[RERANKER WARNING] "
                    f"Using RRF ranking instead: {exc}"
                )

        results = []

        for item in candidates[:top_k]:

            original = item["item"]

            results.append({
                "text": original["text"],
                "source": original["source"],
                "chunk_id": original["chunk_id"],
                "score": round(
                    float(
                        item.get(
                            "rerank_score",
                            item["rrf"]
                        )
                    ),
                    6
                ),
                "rrf_score": round(
                    float(item["rrf"]),
                    8
                ),
                "rerank_score": (
                    round(float(item["rerank_score"]), 6)
                    if "rerank_score" in item else None
                )
            })

    else:

        raise ValueError(
            "Invalid retrieval_mode. "
            "Use vector, bm25, or hybrid."
        )

    elapsed = time.perf_counter() - start_time

    return {
        "results": results,
        "retrieval_seconds": round(elapsed, 4),
        "retrieval_mode": retrieval_mode,
        "reranking_enabled": (
            retrieval_mode == "hybrid" and use_reranker
        )
    }


# --------------------------------------------------
# BACKWARD-COMPATIBLE FUNCTION
# --------------------------------------------------

def hybrid_search(query, top_k=8):
    """
    Keeps existing calls working.
    Defaults to hybrid retrieval with reranking.
    """

    return search(
        query=query,
        top_k=top_k,
        retrieval_mode="hybrid",
        use_reranker=True
    )["results"]
