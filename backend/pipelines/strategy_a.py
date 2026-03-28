# backend/pipelines/strategy_a.py

import logging
import time
import uuid
from backend.config import config
from backend.groq_compat import create_chat_completion
from backend.pipelines.retrieval import retrieve_documents_with_provenance

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    category: str | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Embed query and retrieve top-k chunks from Strategy A collection.

    Why we embed the query with the same model used during indexing:
    Embeddings are only comparable within the same vector space.
    If you index with text-embedding-3-small and query with
    text-embedding-ada-002 — the vectors live in different spaces.
    Cosine similarity between them is meaningless.
    Same model = same space = valid comparison.

    Returns list of document strings — the actual chunk text.
    ChromaDB returns results in order of similarity score.
    result['documents'][0] is a list because ChromaDB supports
    batch queries — we query one at a time so we take index [0].
    """
    return retrieve_documents_with_provenance(
        collection_name=config.COLLECTION_STRATEGY_A,
        strategy_label="Strategy A",
        query=query,
        category=category,
    )


def generate(query: str, contexts: list[str]) -> str:
    """
    Generate answer from query and retrieved contexts.

    Prompt design decisions:
    1. Force substantive answers — not single-word verdicts.
       "Yes" alone gives RAGAS nothing to score for faithfulness
       and gives DeepEval no claims to verify. A minimum of
       2-3 sentences ensures real claim-level coverage.

    2. Keep faithfulness constraint strict — only use context.
       This is the core RAG fidelity requirement. External
       knowledge blending corrupts faithfulness scoring.

    3. Abstain only when truly no information exists.
       Previous prompt abstained too aggressively. The new
       threshold: if context mentions the condition even
       indirectly, use it. Only abstain if context is entirely
       about a different topic.

    4. Structure: verdict first, then evidence from context.
       "Yes. [explanation citing context]" gives:
       - benchmark_eval: correct yes/no verdict extraction
       - RAGAS: substantive answer to score relevancy against
       - DeepEval: multiple atomic claims to verify
    """
    context_str = "\n\n".join(contexts)

    system_prompt = """You are a medical information assistant evaluating clinical questions.

Answer using ONLY the information in the provided context.

RESPONSE RULES:
1. If the question has a yes/no answer and context supports it:
   - Start with "Yes." or "No."
   - Follow with 2-4 sentences explaining the evidence from the context.
   - Cite specific details (mechanisms, numbers, recommendations) that appear in the context.

2. If the context only partially addresses the question:
   - Start with "Yes." or "No." based on what the context does say.
   - State what the context supports, then note what it does not address.

3. Only say "I cannot answer this based on the available information." if the context
   is entirely about a different medical condition or topic with no overlap.

STRICT RULES:
- Do not use any knowledge outside the provided context.
- Do not infer drug classes unless the context explicitly states them.
- Do not add recommendations not present in the context.
- Keep your answer under 100 words."""

    user_prompt = f"""Context:
{context_str}

Question: {query}

Answer:"""

    response = create_chat_completion(
        model=config.GENERATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def determine_failure_source(
    context_recall: float,
    faithfulness: float
) -> str:
    """
    Diagnose where in the pipeline the failure occurred.

    context_recall < 0.5:
        Right information was not retrieved.
        LLM never had a chance. Retrieval failure.

    context_recall >= 0.5 and faithfulness < 0.5:
        Right information was retrieved.
        LLM ignored or distorted it. Generation failure.

    Both >= 0.5:
        Pipeline functioned correctly. No failure.
    """
    if context_recall < 0.5:
        return "retrieval"
    elif faithfulness < 0.5:
        return "llm"
    else:
        return "none"


def run(query: str, category: str | None = None) -> dict:
    """
    Execute full Strategy A pipeline for a single query.

    Returns structured result dict containing everything needed
    for FastAPI response, PostgreSQL logging, and frontend display.

    Why we measure latency:
    Latency is a production metric. Strategy C with reranking
    will be slower than Strategy A. Your dashboard should show
    this tradeoff — better faithfulness at higher latency cost.
    That is a real deployment decision teams need to make.
    """
    start_time = time.time()

    # Step 1: Retrieve relevant chunks
    contexts, retrieval_provenance = retrieve(query, category=category)

    # Step 2: Generate answer from contexts
    answer = generate(query, contexts)

    # Step 3: Calculate latency
    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Strategy A pipeline complete — "
        f"latency: {latency_ms:.1f}ms"
    )

    return {
        "run_id": str(uuid.uuid4()),
        "question": query,
        "pipeline_name": "strategy_a_fixed_chunking",
        "answer": answer,
        "contexts": contexts,
        "retrieval_provenance": retrieval_provenance,
        "metrics": {
            "faithfulness": None,       # populated by ragas_runner
            "answer_relevancy": None,   # populated by ragas_runner
            "context_precision": None,  # populated by ragas_runner
            "context_recall": None      # populated by ragas_runner
        },
        "claims": [],           # populated by deepeval_runner
        "failure_source": None, # populated after scores available
        "latency_ms": round(latency_ms, 2)
    }