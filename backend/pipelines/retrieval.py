import logging
import math
import re

import chromadb
import requests
from chromadb.config import Settings

from backend.config import config


logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\b[a-z0-9]{3,}\b")
_STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "among",
    "because",
    "before",
    "between",
    "could",
    "does",
    "during",
    "from",
    "have",
    "into",
    "more",
    "only",
    "same",
    "should",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "used",
    "using",
    "what",
    "when",
    "which",
    "with",
    "would",
}

chroma_client = chromadb.PersistentClient(
    path=config.CHROMA_PERSIST_DIR,
    settings=Settings(anonymized_telemetry=False),
)


def embed_query(query: str) -> list[float]:
    response = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/embeddings",
        json={"model": config.EMBEDDING_MODEL, "prompt": query},
        timeout=config.OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _keyword_overlap_score(query: str, document: str) -> int:
    query_tokens = {
        token
        for token in _TOKEN_RE.findall(query.lower())
        if token not in _STOPWORDS
    }
    if not query_tokens:
        return 0

    document_tokens = set(_TOKEN_RE.findall(document.lower()))
    return len(query_tokens & document_tokens)


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _select_with_mmr(
    *,
    rows: list[dict],
    top_k: int,
    mmr_lambda: float,
    max_similarity: float | None,
) -> list[dict]:
    remaining = rows[:]
    selected = []
    skipped_for_similarity = []

    while remaining and len(selected) < top_k:
        best_index = None
        best_score = None

        for index, row in enumerate(remaining):
            redundancy_penalty = 0.0
            if selected:
                redundancy_penalty = max(
                    _cosine_similarity(row["embedding"], prior["embedding"])
                    for prior in selected
                )

            mmr_score = (
                mmr_lambda * row["query_similarity"]
                - (1 - mmr_lambda) * redundancy_penalty
            )

            if best_score is None or mmr_score > best_score:
                best_index = index
                best_score = mmr_score

        candidate = remaining.pop(best_index)
        candidate["mmr_score"] = best_score

        if max_similarity is not None and selected:
            max_pairwise_similarity = max(
                _cosine_similarity(candidate["embedding"], prior["embedding"])
                for prior in selected
            )
            if max_pairwise_similarity >= max_similarity:
                skipped_for_similarity.append(candidate)
                continue

        selected.append(candidate)

    if len(selected) < top_k:
        for candidate in skipped_for_similarity:
            if len(selected) >= top_k:
                break
            selected.append(candidate)

    return selected


def retrieve_documents(
    *,
    collection_name: str,
    strategy_label: str,
    query: str,
    category: str | None = None,
) -> list[str]:
    documents, _ = retrieve_documents_with_provenance(
        collection_name=collection_name,
        strategy_label=strategy_label,
        query=query,
        category=category,
    )
    return documents


def retrieve_documents_with_provenance(
    *,
    collection_name: str,
    strategy_label: str,
    query: str,
    category: str | None = None,
    use_mmr: bool = False,
    mmr_lambda: float | None = None,
    max_similarity: float | None = None,
) -> tuple[list[str], list[dict]]:
    query_embedding = embed_query(query)
    collection = chroma_client.get_collection(name=collection_name)

    candidate_count = max(
        config.TOP_K,
        config.TOP_K * config.RETRIEVAL_CANDIDATE_MULTIPLIER,
    )
    include_fields = ["documents", "metadatas", "distances"]
    if use_mmr:
        include_fields.append("embeddings")

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": candidate_count,
        "include": include_fields,
    }
    if category:
        query_kwargs["where"] = {"category": category}

    results = collection.query(**query_kwargs)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    raw_embeddings = results.get("embeddings") if use_mmr else None
    if use_mmr and raw_embeddings and raw_embeddings[0]:
        embeddings = raw_embeddings[0]
    else:
        embeddings = [None] * len(documents)

    candidate_rows = []
    seen_documents = set()
    for document, metadata, distance, embedding in zip(
        documents,
        metadatas,
        distances,
        embeddings,
        strict=False,
    ):
        normalized = " ".join(document.split())
        if normalized in seen_documents:
            continue
        seen_documents.add(normalized)
        candidate_rows.append({
            "document": document,
            "metadata": metadata,
            "distance": distance,
            "embedding": embedding,
            "keyword_overlap": _keyword_overlap_score(query, document),
            "query_similarity": (
                _cosine_similarity(query_embedding, embedding)
                if embedding is not None else 1 - float(distance)
            ),
        })

    ranked_rows = sorted(
        candidate_rows,
        key=lambda item: (
            -item["keyword_overlap"],
            item["distance"],
        ),
    )

    if use_mmr:
        ranked_rows = _select_with_mmr(
            rows=ranked_rows,
            top_k=config.TOP_K,
            mmr_lambda=mmr_lambda if mmr_lambda is not None else config.RETRIEVAL_MMR_LAMBDA,
            max_similarity=max_similarity,
        )
    else:
        ranked_rows = ranked_rows[: config.TOP_K]

    final_documents = []
    final_provenance = []
    for reranked_position, row in enumerate(ranked_rows, start=1):
        document = row["document"]
        metadata = row["metadata"]
        distance = row["distance"]
        final_documents.append(document)
        final_provenance.append({
            "record_id": metadata.get("record_id") if metadata else None,
            "category": metadata.get("category") if metadata else None,
            "source_question": metadata.get("source_question") if metadata else None,
            "strategy": metadata.get("strategy") if metadata else None,
            "distance": round(float(distance), 6),
            "keyword_overlap": row["keyword_overlap"],
            "reranked_position": reranked_position,
            "query_similarity": round(float(row["query_similarity"]), 6),
            "mmr_score": (
                round(float(row["mmr_score"]), 6)
                if use_mmr and row.get("mmr_score") is not None else None
            ),
        })

    logger.info(
        "%s retrieved %s chunks for query '%s...'%s",
        strategy_label,
        len(final_documents),
        query[:50],
        f" in category '{category}'" if category else "",
    )
    logger.info(
        "%s candidate distances: %s",
        strategy_label,
        [round(distance, 3) for distance in distances[: config.TOP_K]],
    )
    if use_mmr:
        logger.info(
            "%s applied MMR diversity reranking with lambda=%s and max_similarity=%s",
            strategy_label,
            mmr_lambda if mmr_lambda is not None else config.RETRIEVAL_MMR_LAMBDA,
            max_similarity,
        )

    return final_documents, final_provenance
