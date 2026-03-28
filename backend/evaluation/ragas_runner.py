# backend/evaluation/ragas_runner.py

import logging
import math
import time
from datetime import datetime
from functools import lru_cache
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from backend.groq_compat import get_chat_groq
from backend.config import config
from backend.pipelines.strategy_a import determine_failure_source

logger = logging.getLogger(__name__)

try:
    import nest_asyncio
except ImportError:  # pragma: no cover - dependency should exist at runtime
    nest_asyncio = None


def _patch_event_loop() -> None:
    if nest_asyncio is None:
        logger.warning(
            "nest_asyncio is not installed. RAGAS may fail in nested event-loop environments."
        )
        return

    nest_asyncio.apply()


def _coerce_metric_score(value) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None

# ── LLM Configuration ─────────────────────────────────────────────
# RAGAS uses an LLM internally as the judge for faithfulness
# and answer relevancy. We explicitly configure it to use the
# same model as our generation pipeline.
#
# Why this matters for consistency:
# Different LLM judges produce different scores for the same answer.
# If RAGAS uses GPT-4o and your pipeline uses GPT-4o-mini —
# your faithfulness scores reflect the judge model's capability
# not your pipeline's actual behavior.
# Same model throughout = scores you can trust and reproduce.
#
# Why LangchainLLMWrapper:
# RAGAS expects a LangChain-compatible LLM object.
# We wrap our OpenAI model to make it compatible.

# ChatGroq wraps Groq's API in the LangChain interface RAGAS expects.
# Same model as generation pipeline — consistent judging standard.
# temperature=0 — deterministic judge decisions.
# Same claim must get same verdict on every eval run.
# Non-zero temperature = different scores each run =
# you cannot tell if score change is real or random.
@lru_cache
def get_ragas_llm() -> LangchainLLMWrapper:
    provider = (config.RAGAS_JUDGE_PROVIDER or "ollama").strip().lower()

    if provider == "ollama":
        return LangchainLLMWrapper(
            Ollama(
                model=config.RAGAS_JUDGE_MODEL,
                base_url=config.OLLAMA_BASE_URL,
                temperature=0,
                timeout=config.OLLAMA_REQUEST_TIMEOUT_SECONDS,
            )
        )

    if provider == "groq":
        return LangchainLLMWrapper(get_chat_groq(model=config.RAGAS_JUDGE_MODEL))

    raise ValueError(
        f"Unsupported RAGAS judge provider: {config.RAGAS_JUDGE_PROVIDER}"
    )

@lru_cache
def get_ragas_embeddings() -> LangchainEmbeddingsWrapper:
    # RAGAS uses embeddings internally for answer_relevancy metric.
    # By default it tries OpenAI — we override with Ollama so no
    # OpenAI key is needed. Must match the same model used for indexing.
    return LangchainEmbeddingsWrapper(
        OllamaEmbeddings(
            model=config.EMBEDDING_MODEL,
            base_url=config.OLLAMA_BASE_URL
        )
    )

# Attach configured LLM and embeddings to each metric
# Without this RAGAS uses its default OpenAI — will crash without key
def configure_ragas_metrics() -> None:
    ragas_llm = get_ragas_llm()
    ragas_embeddings = get_ragas_embeddings()
    logger.info(
        "Configured RAGAS judge with provider=%s model=%s",
        config.RAGAS_JUDGE_PROVIDER,
        config.RAGAS_JUDGE_MODEL,
    )
    faithfulness.llm = ragas_llm
    answer_relevancy.llm = ragas_llm
    answer_relevancy.embeddings = ragas_embeddings
    context_precision.llm = ragas_llm
    context_recall.llm = ragas_llm

RAGAS_METRICS = [
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
]


def evaluate_with_ragas(
    question: str,
    answer: str,
    contexts: list[str],
    reference_answer: str,
    run_id: str = None
) -> dict:
    """
    Run RAGAS evaluation on a single pipeline result.

    What RAGAS does internally for each metric:

    Faithfulness:
        LLM extracts atomic claims from answer.
        For each claim, LLM asks: supported by contexts?
        Score = supported_claims / total_claims

    Answer Relevancy:
        LLM generates N questions that the answer implies.
        Measures cosine similarity between those generated
        questions and the original question.
        Score = avg similarity across generated questions.
        High score = answer directly addresses the question.

    Context Precision:
        Of the retrieved chunks, how many were actually useful?
        Measures signal-to-noise ratio of retrieval.
        Low score = you retrieved lots of irrelevant chunks.

    Context Recall:
        Does the retrieved context contain all information
        needed to answer the question fully?
        Measured against reference_answer as ground truth.
        Low score = retrieval missed important information.

    Args:
        question: original medical question
        answer: generated answer from pipeline
        contexts: list of retrieved chunks
        reference_answer: PubMedQA long_answer as ground truth
        run_id: for logging — links eval result to pipeline run

    Returns:
        dict with 4 metric scores + failure_source diagnosis
        + evaluated_at timestamp
    """
    logger.info(
        f"Starting RAGAS evaluation — "
        f"run_id: {run_id}, "
        f"question: '{question[:60]}...'"
    )

    start_time = time.time()

    try:
        _patch_event_loop()
        configure_ragas_metrics()

        # RAGAS expects batched input even for single samples
        # Each value must be a list — this is RAGAS API design
        # not our choice. Wrapping in list = batch of size 1.
        data = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],     # list of lists
            "ground_truth": [reference_answer]
        }

        dataset = Dataset.from_dict(data)

        result = evaluate(
            dataset=dataset,
            metrics=RAGAS_METRICS,
            raise_exceptions=False
        )

        # Convert to pandas for clean extraction
        # iloc[0] — we only have one row (single sample)
        scores_df = result.to_pandas()
        scores = scores_df.iloc[0].to_dict()

        # Extract with explicit float casting
        # RAGAS sometimes returns numpy floats — PostgreSQL
        # expects Python native floats. Cast explicitly.
        faithfulness_score = _coerce_metric_score(scores.get("faithfulness"))
        answer_relevancy_score = _coerce_metric_score(scores.get("answer_relevancy"))
        context_precision_score = _coerce_metric_score(scores.get("context_precision"))
        context_recall_score = _coerce_metric_score(scores.get("context_recall"))

        # Derive failure source using logic you built
        failure_source = None
        if faithfulness_score is not None and context_recall_score is not None:
            failure_source = determine_failure_source(
                context_recall=context_recall_score,
                faithfulness=faithfulness_score
            )

        eval_time = time.time() - start_time

        logger.info(
            f"RAGAS evaluation complete — "
            f"run_id: {run_id}, "
            f"faithfulness: {faithfulness_score}, "
            f"recall: {context_recall_score}, "
            f"failure_source: {failure_source}, "
            f"eval_time: {eval_time:.1f}s"
        )

        return {
            "faithfulness": faithfulness_score,
            "answer_relevancy": answer_relevancy_score,
            "context_precision": context_precision_score,
            "context_recall": context_recall_score,
            "failure_source": failure_source,
            "evaluated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        # Never let eval failure crash the pipeline run
        # Log the error, return None scores, mark as failed
        # The run result still gets saved — just without scores
        # You can re-run eval later without re-running the pipeline
        logger.exception(
            f"RAGAS evaluation failed — "
            f"run_id: {run_id}, "
            f"error: {str(e)}"
        )

        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None,
            "failure_source": None,
            "evaluated_at": datetime.utcnow().isoformat(),
            "error": str(e)
        }


def batch_evaluate(pipeline_results: list[dict], testset: list[dict]) -> list[dict]:
    """
    Run RAGAS evaluation across all pipeline results.

    pipeline_results: list of run() outputs from strategy files
    testset: qa_pairs.json loaded as list of dicts

    Why we match by question text not index:
    Pipeline results and testset may not be in same order.
    Matching by question string is explicit and safe.
    Index matching breaks silently if order shifts.

    Returns pipeline_results with metrics populated.
    """
    # Build lookup: question → reference answer
    # O(1) lookup per result instead of O(n) search
    reference_lookup = {
        item["question"]: item["reference_answer"]
        for item in testset
    }

    evaluated_results = []

    for i, result in enumerate(pipeline_results):
        question = result["question"]
        reference_answer = reference_lookup.get(question)

        if not reference_answer:
            logger.warning(
                f"No reference answer found for question: "
                f"'{question[:60]}...' — skipping eval"
            )
            evaluated_results.append(result)
            continue

        logger.info(
            f"Evaluating result {i + 1}/{len(pipeline_results)} — "
            f"pipeline: {result['pipeline_name']}"
        )

        scores = evaluate_with_ragas(
            question=question,
            answer=result["answer"],
            contexts=result["contexts"],
            reference_answer=reference_answer,
            run_id=result["run_id"]
        )

        # Merge scores into result dict
        result["metrics"].update({
            "faithfulness": scores["faithfulness"],
            "answer_relevancy": scores["answer_relevancy"],
            "context_precision": scores["context_precision"],
            "context_recall": scores["context_recall"]
        })
        result["failure_source"] = scores["failure_source"]

        evaluated_results.append(result)

    return evaluated_results

'''
## What I added beyond your draft and why

| Addition | Reason |
|---|---|
| Explicit LLM config on metrics | Reproducible scores — same judge every run |
| temperature=0 on judge | Deterministic verdicts — no random variance |
| float() casting on scores | PostgreSQL rejects numpy floats |
| try/except with graceful degradation | Eval failure never kills pipeline run |
| batch_evaluate with question lookup | O(1) matching, order-independent |
| eval timing logged | Debugging slow eval runs |
| error field in failure return | You know why a score is None |

---

## Progress card — save this
```
MEDRAG EVAL — PROGRESS CARD v5

Completed:
✓ config.py
✓ fetcher.py (ChatDoctor + PubMedQA)
✓ indexer.py (3 chunking strategies)
✓ strategy_a/b/c.py (3 pipelines)
✓ db/models.py + db/session.py
✓ ragas_runner.py (4 metrics + batch eval)

Next:
→ deepeval_runner.py (claim-level breakdown)
→ trulens_runner.py (pipeline tracing)
→ main.py (FastAPI — 4 endpoints)
→ React frontend (4 pages)

Key decisions:
- RAGAS LLM judge = same model as pipeline (reproducibility)
- temperature=0 on judge (deterministic scoring)
- Eval failure degrades gracefully (run saved, scores None)
- Question-based lookup not index-based (order-safe)
'''
