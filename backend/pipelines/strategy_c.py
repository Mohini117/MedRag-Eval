# backend/pipelines/strategy_c.py

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
    Embed query and retrieve from Strategy C collection.

    Strategy C uses parent-child indexing architecture:
    - CHILD chunks (100 words) were embedded during indexing
      Small size = precise embedding = accurate similarity search
    - PARENT chunks (400 words) were stored as documents

    What this means for retrieval:
    ChromaDB computes similarity against child embeddings —
    so retrieval precision is high (small focused vectors).
    But results['documents'] returns parent text —
    so the LLM receives full clinical context not fragments.

    The retrieval code is identical to A and B.
    The difference is invisible here — it happened at index time.
    This is the architectural trick: decouple retrieval unit
    from context unit. Best of both worlds.

    Expected outcome: highest faithfulness score of all three
    strategies because LLM never receives incomplete chunks.
    """
    return retrieve_documents_with_provenance(
        collection_name=config.COLLECTION_STRATEGY_C,
        strategy_label="Strategy C",
        query=query,
        category=category,
        use_mmr=config.STRATEGY_C_ENABLE_DIVERSITY_RERANKING,
        mmr_lambda=config.RETRIEVAL_MMR_LAMBDA,
        max_similarity=config.RETRIEVAL_MAX_SIMILARITY,
    )


def run(query: str, category: str | None = None) -> dict:
    """
    Execute full Strategy C pipeline for a single query.
    Parent-child corpus — expected to outperform A and B on
    faithfulness due to complete context delivered to LLM.
    Higher latency than A and B is acceptable tradeoff.
    """
    start_time = time.time()

    contexts, retrieval_provenance = retrieve(query, category=category)
    answer = generate(query, contexts)

    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Strategy C pipeline complete — "
        f"latency: {latency_ms:.1f}ms"
    )

    return {
        "run_id": str(uuid.uuid4()),
        "question": query,
        "pipeline_name": "strategy_c_parent_child_chunking",
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


''''

## Progress card — save this for new chat if needed
```
MEDRAG EVAL — PROGRESS CARD v3

Completed:
✓ config.py
✓ fetcher.py (ChatDoctor corpus + PubMedQA eval testset)
✓ indexer.py (fixed + semantic + parent-child + ChromaDB)
✓ strategy_a.py (fixed chunking pipeline)
✓ strategy_b.py (semantic chunking pipeline)
✓ strategy_c.py (parent-child pipeline)

Next immediate step:
→ db/models.py — PostgreSQL schema for logging eval results
→ ragas_runner.py — compute 4 RAGAS metrics per run
→ deepeval_runner.py — claim-level hallucination breakdown
→ trulens_runner.py — trace retrieval vs LLM failure

Key architectural decisions made:
- Corpus: ChatDoctor only (no leakage)
- Eval set: PubMedQA yes/no balanced 15/15 frozen to disk
- Parent-child: child embedded, parent returned to LLM
- temperature=0 for deterministic eval
- failure_source logic: recall<0.5=retrieval, faith<0.5=llm

Stack: FastAPI + ChromaDB + PostgreSQL + OpenAI
'''
