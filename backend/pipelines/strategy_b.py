# backend/pipelines/strategy_b.py

import logging
import time
import uuid
from backend.config import config
from backend.pipelines.retrieval import retrieve_documents_with_provenance
from backend.pipelines.strategy_a import generate

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    category: str | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Embed query and retrieve top-k chunks from Strategy B collection.

    Strategy B collection was indexed using semantic chunking —
    chunks respect natural topic boundaries in medical text.
    Retrieved chunks are more semantically coherent than Strategy A
    because they were never split mid-topic.

    Retrieval mechanism is identical to Strategy A — the difference
    is entirely in what was indexed, not how we query.
    Better chunks in = better context out = higher faithfulness expected.
    """
    return retrieve_documents_with_provenance(
        collection_name=config.COLLECTION_STRATEGY_B,
        strategy_label="Strategy B",
        query=query,
        category=category,
    )


def run(query: str, category: str | None = None) -> dict:
    """
    Execute full Strategy B pipeline for a single query.
    Semantic chunking corpus — expected to outperform Strategy A
    on context precision and faithfulness due to coherent chunks.
    """
    start_time = time.time()

    contexts, retrieval_provenance = retrieve(query, category=category)
    answer = generate(query, contexts)

    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Strategy B pipeline complete — "
        f"latency: {latency_ms:.1f}ms"
    )

    return {
        "run_id": str(uuid.uuid4()),
        "question": query,
        "pipeline_name": "strategy_b_semantic_chunking",
        "answer": answer,
        "contexts": contexts,
        "retrieval_provenance": retrieval_provenance,
        "metrics": {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None
        },
        "claims": [],
        "failure_source": None,
        "latency_ms": round(latency_ms, 2)
    }
