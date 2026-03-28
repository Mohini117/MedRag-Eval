# backend/main.py

import json
import logging
import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config import config
from backend.db.session import get_db, initialize_database, check_database_connection
from backend.evaluation.benchmark_metrics import evaluate_binary_answer
from backend.db.models import (
    Run,
    Metric,
    Claim,
    Trace,
    PipelineName,
    ClaimStatus,
    FailureSource,
)
from backend.pipelines import strategy_a, strategy_b, strategy_c
from backend.pipelines.strategy_a import determine_failure_source

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BENCHMARK_RESULTS_PATH = Path("backend/testset/benchmark_results.json")
BENCHMARK_PROGRESS_PATH = Path("backend/testset/benchmark_progress.json")
BENCHMARK_METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def sanitize_json_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {
            key: sanitize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    return value


def coerce_finite_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def safe_round(value: Optional[float], digits: int) -> Optional[float]:
    numeric = coerce_finite_float(value)
    return round(numeric, digits) if numeric is not None else None


def mean_or_none(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def load_benchmark_results_file() -> list[dict]:
    if not BENCHMARK_RESULTS_PATH.exists():
        return []

    with open(BENCHMARK_RESULTS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise HTTPException(
            status_code=500,
            detail="Benchmark results file is not a JSON array."
        )

    return sanitize_json_value(data)


def build_benchmark_summary(results: list[dict]) -> dict:
    strategy_stats = {}
    categories = set()
    sources = set()

    for item in results:
        category = item.get("category")
        source = item.get("source")
        if category:
            categories.add(category)
        if source:
            sources.add(source)

        for run_result in item.get("results", []):
            pipeline_name = run_result.get("pipeline_name")
            if not pipeline_name:
                continue

            stats = strategy_stats.setdefault(
                pipeline_name,
                {
                    "metric_values": defaultdict(list),
                    "latency_values": [],
                    "correct_values": [],
                    "abstained_values": [],
                    "failure_distribution": Counter(),
                    "run_count": 0,
                }
            )
            stats["run_count"] += 1

            metrics = run_result.get("metrics", {})
            for metric_key in BENCHMARK_METRIC_KEYS:
                metric_value = coerce_finite_float(metrics.get(metric_key))
                if metric_value is not None:
                    stats["metric_values"][metric_key].append(metric_value)

            latency_value = coerce_finite_float(run_result.get("latency_ms"))
            if latency_value is not None:
                stats["latency_values"].append(latency_value)

            benchmark_eval = run_result.get("benchmark_eval", {})
            is_correct = benchmark_eval.get("is_correct")
            if is_correct is not None:
                stats["correct_values"].append(1.0 if is_correct else 0.0)

            is_abstained = benchmark_eval.get("is_abstained")
            if is_abstained is not None:
                stats["abstained_values"].append(1.0 if is_abstained else 0.0)

            failure_source = (
                run_result.get("failure_source")
                or metrics.get("failure_source")
            )
            if failure_source:
                stats["failure_distribution"][failure_source] += 1

    summary = []
    for pipeline_name, stats in sorted(strategy_stats.items()):
        summary.append(
            {
                "pipeline_name": pipeline_name,
                "run_count": stats["run_count"],
                "metrics": {
                    metric_key: safe_round(
                        mean_or_none(stats["metric_values"][metric_key]),
                        3,
                    )
                    for metric_key in BENCHMARK_METRIC_KEYS
                },
                "avg_latency_ms": safe_round(
                    mean_or_none(stats["latency_values"]),
                    1,
                ),
                "verdict_accuracy": safe_round(
                    mean_or_none(stats["correct_values"]),
                    3,
                ),
                "abstain_rate": safe_round(
                    mean_or_none(stats["abstained_values"]),
                    3,
                ),
                "failure_distribution": dict(stats["failure_distribution"]),
            }
        )

    return {
        "total_questions": len(results),
        "total_runs": sum(item["run_count"] for item in summary),
        "summary": summary,
        "categories_available": sorted(categories),
        "sources_available": sorted(sources),
    }

# ── App Initialization ────────────────────────────────────────────

app = FastAPI(
    title="MedRAG Eval API",
    description="Benchmarking RAG pipeline strategies on medical QA data",
    version="1.0.0"
)

# CORS — allows React frontend to call this API
# In production restrict origins to your actual frontend domain
# For development allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """
    Run once when FastAPI starts.
    Creates all database tables if they don't exist.
    Safe to run multiple times — create_all is idempotent.
    """
    if check_database_connection():
        initialize_database()
        app.state.db_ready = True
        logger.info("MedRAG Eval API started — database initialized")
    else:
        app.state.db_ready = False
        logger.warning(
            "MedRAG Eval API started without a database connection. "
            "Start PostgreSQL on localhost:5432 to enable DB-backed endpoints."
        )


# ── Request / Response Models ─────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    reference_answer: str
    category: Optional[str] = None
    final_answer: Optional[str] = None
    source: Optional[str] = None
    enable_ragas: bool = True
    enable_deepeval: bool = True
    enable_trulens: bool = False
    # reference_answer required at request time because:
    # RAGAS needs ground truth to compute context_recall
    # In production this comes from your frozen qa_pairs.json
    # Frontend sends it alongside the question


class RunFilters(BaseModel):
    pipeline_name: Optional[str] = None
    category: Optional[str] = None
    max_faithfulness: Optional[float] = None
    # max_faithfulness filter — powers Failure Explorer
    # "show me all runs where faithfulness < 0.5"
    min_faithfulness: Optional[float] = None
    limit: int = 50


# ── Helper: Persist Full Run to PostgreSQL ────────────────────────

def persist_run(
    result: dict,
    ragas_metrics: dict,
    claims: list[dict],
    trace_data: dict,
    category: Optional[str],
    db: Session
) -> None:
    """
    Persist a complete pipeline run to PostgreSQL.

    Write order matters:
    1. Run first — parent record must exist before children
    2. Metric — references run_id
    3. Claims — each references run_id
    4. Trace — references run_id

    Why single transaction:
    All four inserts succeed together or all fail together.
    Partial writes leave orphaned records that corrupt your
    Failure Explorer and Trace Viewer queries.
    SQLAlchemy session is the transaction boundary —
    commit() at the end applies all inserts atomically.
    """
    result = sanitize_json_value(result)
    ragas_metrics = sanitize_json_value(ragas_metrics)
    trace_data = sanitize_json_value(trace_data)

    run_id = uuid.UUID(result["run_id"])

    # 1. Run record
    run = Run(
        id=run_id,
        question=result["question"],
        pipeline_name=PipelineName(result["pipeline_name"]),
        answer=result["answer"],
        category=category,
        latency_ms=result["latency_ms"],
        created_at=datetime.utcnow()
    )
    db.add(run)

    # 2. Metrics record
    faithfulness = ragas_metrics.get("faithfulness")
    context_recall = ragas_metrics.get("context_recall")
    failure_source = infer_failure_source(ragas_metrics)

    metric = Metric(
        id=uuid.uuid4(),
        run_id=run_id,
        faithfulness=faithfulness,
        answer_relevancy=ragas_metrics.get("answer_relevancy"),
        context_precision=ragas_metrics.get("context_precision"),
        context_recall=context_recall,
        failure_source=FailureSource(failure_source) if failure_source else None,
        evaluated_at=datetime.utcnow()
    )
    db.add(metric)

    # 3. Claims records — one row per claim
    for claim in claims:
        claim_record = Claim(
            id=uuid.uuid4(),
            run_id=run_id,
            claim_text=claim["claim_text"],
            status=ClaimStatus(claim["status"]),
            claim_index=claim["claim_index"],
            supporting_context=claim.get("supporting_context")
        )
        db.add(claim_record)

    # 4. Trace record
    trace_failure_source = trace_data.get("failure_source")
    trace = Trace(
        id=uuid.uuid4(),
        run_id=run_id,
        retrieved_contexts=trace_data.get("retrieved_contexts", result.get("contexts", [])),
        context_count=trace_data.get("context_count", len(result.get("contexts", []))),
        groundedness_score=trace_data.get("groundedness_score"),
        context_relevance_min=trace_data.get("context_relevance_min"),
        answer_relevance=trace_data.get("answer_relevance"),
        failure_source=FailureSource(trace_failure_source) if trace_failure_source else None,
        trace_id=trace_data.get("trace_id"),
        trulens_feedback=trace_data.get("trulens_feedback"),
        raw_pipeline_output=json.dumps(result, allow_nan=False),
        created_at=datetime.utcnow()
    )
    db.add(trace)

    # Single commit — atomic write
    db.commit()

    logger.info(
        f"Persisted run {run_id} — "
        f"pipeline: {result['pipeline_name']}, "
        f"faithfulness: {faithfulness}"
    )


# ── Endpoint 1: POST /run-query ───────────────────────────────────

STRATEGY_MAP = {
    "strategy_a": "strategy_a",
    "strategy_b": "strategy_b",
    "strategy_c": "strategy_c"
}

PIPELINE_NAME_MAP = {
    "strategy_a": "strategy_a_fixed_chunking",
    "strategy_b": "strategy_b_semantic_chunking",
    "strategy_c": "strategy_c_parent_child_chunking",
}


def infer_failure_source(ragas_metrics: dict) -> Optional[str]:
    faithfulness = ragas_metrics.get("faithfulness")
    context_recall = ragas_metrics.get("context_recall")
    if faithfulness is None or context_recall is None:
        return None
    return determine_failure_source(
        context_recall=context_recall,
        faithfulness=faithfulness
    )


def build_benchmark_eval(answer: Optional[str], expected_answer: Optional[str]) -> dict:
    return evaluate_binary_answer(
        answer=answer,
        expected_label=expected_answer,
    )


def build_fallback_trace_for_storage(
    result: dict,
    ragas_metrics: dict,
    run_id: str,
    trace_error: Optional[Exception] = None
) -> dict:
    return {
        "run_id": run_id,
        "retrieved_contexts": result.get("contexts", []),
        "context_count": len(result.get("contexts", [])),
        "trulens_feedback": str(result.get("trulens", {})),
        "groundedness_score": result.get("trulens", {}).get("groundedness"),
        "context_relevance_min": result.get("trulens", {}).get("context_relevance_min"),
        "answer_relevance": result.get("trulens", {}).get("answer_relevance"),
        "failure_source": infer_failure_source(ragas_metrics),
        "trace_id": result.get("trulens", {}).get("trace_id"),
        "error": str(trace_error) if trace_error else result.get("trulens", {}).get("error"),
        "created_at": datetime.utcnow().isoformat()
    }


# Minimum word count for DeepEval to be worth running.
# A single-word answer like "Yes" has no atomic claims to verify.
# Threshold: 10 words. Below this, DeepEval returns empty or
# trivial claims that add noise to the Failure Explorer.
_DEEPEVAL_MIN_WORD_COUNT = 10

# Delay between strategies to respect Groq rate limits.
# Each strategy triggers: 1 pipeline call + up to 4 RAGAS judge
# calls + 2 DeepEval calls = ~7 Groq calls per strategy.
# 8 seconds gives the token bucket time to partially refill
# before the next strategy's burst, without making the total
# request unbearably slow (3 strategies × 8s = +24s overhead).
_INTER_STRATEGY_DELAY_SECONDS = 15


@app.post("/run-query")
def run_query(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """
    Run question through all 3 RAG pipelines.
    For each pipeline:
    1. Execute pipeline (with optional TruLens tracing)
    2. Evaluate with RAGAS (4 metrics)
    3. Evaluate with DeepEval (claim-level) — skipped if abstain or short answer
    4. Persist everything to PostgreSQL
    5. Return combined results

    Why sequential not parallel:
    Groq rate limits. Running 3 pipelines + 3 eval suites
    simultaneously saturates the token bucket and causes
    silent failures (null scores). Sequential with a short
    inter-strategy delay is slower but produces complete results.

    Why Depends(get_db):
    FastAPI dependency injection. get_db() yields a session,
    FastAPI ensures it closes after request completes.
    Never instantiate sessions directly in endpoint functions.
    """
    import time as _time

    logger.info(
        f"Received query: '{request.question[:60]}...'"
    )

    final_results = []
    strategies = ["strategy_a", "strategy_b", "strategy_c"]

    for strategy_index, strategy_name in enumerate(strategies):
        # Rate-limit buffer between strategies.
        # Skip delay before the first strategy — no previous burst to recover from.
        if strategy_index > 0 and request.enable_ragas:
            logger.info(
                f"Waiting {_INTER_STRATEGY_DELAY_SECONDS}s before {strategy_name} "
                f"to respect Groq rate limits..."
            )
            _time.sleep(_INTER_STRATEGY_DELAY_SECONDS)

        logger.info(f"Running {strategy_name} [{strategy_index + 1}/3]")
        strategy_module = {
            "strategy_a": strategy_a,
            "strategy_b": strategy_b,
            "strategy_c": strategy_c
        }[strategy_name]

        try:
            # Step 1: Run pipeline with optional TruLens instrumentation
            trace_error = None
            if request.enable_trulens:
                try:
                    from backend.evaluation.trulens_runner import (
                        run_with_tracing,
                        build_trace_for_storage
                    )

                    result = run_with_tracing(
                        question=request.question,
                        strategy=strategy_name,
                        run_id=None,
                        category=request.category
                    )
                except Exception as exc:
                    trace_error = exc
                    logger.warning(
                        f"TruLens unavailable for {strategy_name}: {str(exc)}"
                    )
                    result = strategy_module.run(
                        request.question,
                        category=request.category
                    )
                    result["trulens"] = {
                        "groundedness": None,
                        "context_relevance_min": None,
                        "answer_relevance": None,
                        "trace_id": None,
                        "error": f"TruLens unavailable: {str(exc)}"
                    }
            else:
                result = strategy_module.run(
                    request.question,
                    category=request.category
                )
                result["trulens"] = {
                    "groundedness": None,
                    "context_relevance_min": None,
                    "answer_relevance": None,
                    "trace_id": None,
                    "error": None
                }

            logger.info(
                f"{strategy_name} answer ({len(result['answer'].split())} words): "
                f"'{result['answer'][:80]}...'"
            )

            # Step 2: RAGAS evaluation
            ragas_metrics = {
                "faithfulness": None,
                "answer_relevancy": None,
                "context_precision": None,
                "context_recall": None,
                "failure_source": None,
                "evaluated_at": datetime.utcnow().isoformat(),
            }
            if request.enable_ragas:
                from backend.evaluation.ragas_runner import evaluate_with_ragas

                ragas_metrics = evaluate_with_ragas(
                    question=request.question,
                    answer=result["answer"],
                    contexts=result["contexts"],
                    reference_answer=request.reference_answer,
                    run_id=result["run_id"]
                )
                ragas_metrics = sanitize_json_value(ragas_metrics)

                # Merge RAGAS scores into result metrics dict
                result["metrics"].update(ragas_metrics)

            benchmark_eval = build_benchmark_eval(
                answer=result.get("answer"),
                expected_answer=request.final_answer,
            )

            # Step 3: DeepEval claim-level evaluation
            # Skip conditions:
            # (a) LLM abstained — "I cannot answer" has no verifiable claims.
            #     Marking abstain-claims as hallucinated is a false positive.
            # (b) Answer is too short — single-word answers like "Yes" produce
            #     trivial or empty claim sets that pollute the Failure Explorer.
            #     Minimum threshold: _DEEPEVAL_MIN_WORD_COUNT words.
            claims = []
            if request.enable_deepeval:
                answer_text = result.get("answer") or ""
                answer_word_count = len(answer_text.split())
                is_abstained = benchmark_eval.get("is_abstained", False)
                is_too_short = answer_word_count < _DEEPEVAL_MIN_WORD_COUNT

                if is_abstained:
                    logger.info(
                        f"{strategy_name}: skipping DeepEval — answer is abstain"
                    )
                elif is_too_short:
                    logger.info(
                        f"{strategy_name}: skipping DeepEval — answer too short "
                        f"({answer_word_count} words, min {_DEEPEVAL_MIN_WORD_COUNT})"
                    )
                else:
                    from backend.evaluation.deepeval_runner import evaluate_with_deepeval
                    claims = evaluate_with_deepeval(
                        answer=answer_text,
                        contexts=result["contexts"],
                        run_id=result["run_id"]
                    )
                    logger.info(
                        f"{strategy_name}: DeepEval produced {len(claims)} claims"
                    )

            result["claims"] = claims

            # Step 4: Build trace for storage
            if request.enable_trulens and trace_error is None:
                trace_data = build_trace_for_storage(
                    result=result,
                    ragas_metrics=ragas_metrics,
                    run_id=result["run_id"]
                )
            else:
                trace_data = build_fallback_trace_for_storage(
                    result=result,
                    ragas_metrics=ragas_metrics,
                    run_id=result["run_id"],
                    trace_error=trace_error
                )

            # Step 5: Set failure source on result
            result["failure_source"] = (
                trace_data["failure_source"]
                or ragas_metrics.get("failure_source")
            )
            result["benchmark_eval"] = benchmark_eval

            logger.info(
                f"{strategy_name} complete — "
                f"faithfulness={ragas_metrics.get('faithfulness')}, "
                f"recall={ragas_metrics.get('context_recall')}, "
                f"failure_source={result['failure_source']}, "
                f"claims={len(claims)}"
            )

            # Step 6: Persist to PostgreSQL
            persist_run(
                result=result,
                ragas_metrics=ragas_metrics,
                claims=claims,
                trace_data=trace_data,
                category=request.category,
                db=db
            )

            final_results.append(sanitize_json_value(result))

        except Exception as e:
            db.rollback()
            logger.error(
                f"Pipeline {strategy_name} failed: {str(e)}", exc_info=True
            )
            # Don't crash entire request if one strategy fails.
            # Return partial results — frontend shows what succeeded.
            final_results.append(sanitize_json_value({
                "pipeline_name": PIPELINE_NAME_MAP[strategy_name],
                "run_id": str(uuid.uuid4()),
                "answer": None,
                "contexts": [],
                "retrieval_provenance": [],
                "metrics": {
                    "faithfulness": None,
                    "answer_relevancy": None,
                    "context_precision": None,
                    "context_recall": None,
                },
                "claims": [],
                "failure_source": None,
                "latency_ms": None,
                "benchmark_eval": build_benchmark_eval(
                    answer=None,
                    expected_answer=request.final_answer,
                ),
                "error": str(e),
                "question": request.question
            }))

    return sanitize_json_value({
        "question": request.question,
        "source": request.source,
        "results": final_results,
        "total_strategies": len(strategies),
        "successful": len([r for r in final_results if "error" not in r])
    })


# ── Endpoint 2: GET /runs ─────────────────────────────────────────

@app.get("/runs")
def get_runs(
    pipeline_name: Optional[str] = None,
    category: Optional[str] = None,
    max_faithfulness: Optional[float] = None,
    min_faithfulness: Optional[float] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Fetch paginated run history with metrics.
    Powers Failure Explorer — filterable by pipeline and scores.

    Why query params not request body for GET:
    GET requests carry no body by convention.
    Filters go in query string: /runs?max_faithfulness=0.5
    This is REST convention — GET = read, filters = query params.

    Why join runs and metrics in one query:
    Frontend needs both run data and scores in one response.
    Two separate queries = two round trips = slower.
    SQLAlchemy join = one query = one round trip.
    """
    query = db.query(Run, Metric).join(
        Metric, Run.id == Metric.run_id
    )

    # Apply filters
    if pipeline_name:
        query = query.filter(Run.pipeline_name == pipeline_name)

    if category:
        query = query.filter(Run.category == category)

    if max_faithfulness is not None:
        # This is the Failure Explorer filter
        # "show me runs where faithfulness is below threshold"
        query = query.filter(
            Metric.faithfulness <= max_faithfulness
        )

    if min_faithfulness is not None:
        query = query.filter(
            Metric.faithfulness >= min_faithfulness
        )

    # Order by most recent first
    query = query.order_by(Run.created_at.desc()).limit(limit)

    rows = query.all()

    return sanitize_json_value({
        "runs": [
            {
                "run_id": str(run.id),
                "question": run.question,
                "pipeline_name": run.pipeline_name.value,
                "category": run.category,
                "latency_ms": run.latency_ms,
                "created_at": run.created_at.isoformat(),
                "metrics": {
                    "faithfulness": metric.faithfulness,
                    "answer_relevancy": metric.answer_relevancy,
                    "context_precision": metric.context_precision,
                    "context_recall": metric.context_recall,
                    "failure_source": metric.failure_source.value
                    if metric.failure_source else None
                }
            }
            for run, metric in rows
        ],
        "total": len(rows)
    })


# ── Endpoint 3: GET /runs/{run_id} ────────────────────────────────

@app.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch complete details for a single run.
    Powers Trace Viewer — shows full pipeline execution.

    Fetches: run + metrics + claims + trace in one response.
    Why not lazy load separately:
    Trace Viewer needs all of this simultaneously to render
    the complete pipeline trace. Four queries vs one response
    — we accept the larger payload for simpler frontend logic.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run_id format: {run_id}"
        )

    run = db.query(Run).filter(Run.id == run_uuid).first()

    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )

    metric = db.query(Metric).filter(
        Metric.run_id == run_uuid
    ).first()

    claims = db.query(Claim).filter(
        Claim.run_id == run_uuid
    ).order_by(Claim.claim_index).all()
    # order_by claim_index — frontend renders claims in answer order
    # Without ordering, claims appear randomly

    trace = db.query(Trace).filter(
        Trace.run_id == run_uuid
    ).first()
    raw_pipeline_output = {}
    if trace and trace.raw_pipeline_output:
        try:
            raw_pipeline_output = json.loads(trace.raw_pipeline_output)
        except Exception:
            raw_pipeline_output = {}

    return sanitize_json_value({
        "run_id": run_id,
        "question": run.question,
        "pipeline_name": run.pipeline_name.value,
        "answer": run.answer,
        "category": run.category,
        "latency_ms": run.latency_ms,
        "created_at": run.created_at.isoformat(),
        "metrics": {
            "faithfulness": metric.faithfulness if metric else None,
            "answer_relevancy": metric.answer_relevancy if metric else None,
            "context_precision": metric.context_precision if metric else None,
            "context_recall": metric.context_recall if metric else None,
            "failure_source": metric.failure_source.value
            if metric and metric.failure_source else None
        },
        "claims": [
            {
                "claim_text": c.claim_text,
                "claim_index": c.claim_index,
                "status": c.status.value,
                "supporting_context": c.supporting_context
            }
            for c in claims
        ],
        "trace": {
            "retrieved_contexts": trace.retrieved_contexts if trace else [],
            "context_count": trace.context_count if trace else 0,
            "retrieval_provenance": raw_pipeline_output.get("retrieval_provenance", []),
            "groundedness_score": trace.groundedness_score if trace else None,
            "context_relevance_min": trace.context_relevance_min if trace else None,
            "answer_relevance": trace.answer_relevance if trace else None,
            "trace_id": trace.trace_id if trace else None,
            "trulens_feedback": trace.trulens_feedback if trace else None,
            "failure_source": metric.failure_source.value
            if metric and metric.failure_source else None
        }
    })


# ── Endpoint 4: GET /metrics/summary ─────────────────────────────

@app.get("/metrics/summary")
def get_metrics_summary(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Aggregated metrics per strategy for Score Heatmap page.

    Groups all runs by pipeline_name and computes averages.
    Returns one row per strategy — 3 rows total.

    Why func.avg not Python averaging:
    func.avg runs in PostgreSQL — database does the math.
    Loading all runs into Python and averaging there would
    be slow and memory-intensive as run count grows.
    Always push aggregations to the database.

    Why func.count:
    Heatmap should show how many runs each average is based on.
    An average from 3 runs is much less reliable than one
    from 300 runs. Count gives the viewer context.
    """
    query = (
        db.query(
            Run.pipeline_name,
            func.avg(Metric.faithfulness).label("avg_faithfulness"),
            func.avg(Metric.answer_relevancy).label("avg_answer_relevancy"),
            func.avg(Metric.context_precision).label("avg_context_precision"),
            func.avg(Metric.context_recall).label("avg_context_recall"),
            func.avg(Run.latency_ms).label("avg_latency_ms"),
            func.count(Run.id).label("run_count")
        )
        .join(Metric, Run.id == Metric.run_id)
        .group_by(Run.pipeline_name)
    )

    if category:
        query = query.filter(Run.category == category)

    rows = query.all()

    # Build heatmap data structure
    # Frontend expects list of strategy objects
    # Each object has all metric averages for that strategy
    summary = []
    for row in rows:
        summary.append({
            "pipeline_name": row.pipeline_name.value,
            "run_count": row.run_count,
            "metrics": {
                "faithfulness": safe_round(row.avg_faithfulness, 3),
                "answer_relevancy": safe_round(row.avg_answer_relevancy, 3),
                "context_precision": safe_round(row.avg_context_precision, 3),
                "context_recall": safe_round(row.avg_context_recall, 3)
            },
            "avg_latency_ms": safe_round(row.avg_latency_ms, 1)
        })

    # Failure source distribution per strategy
    # Adds diagnostic depth to the heatmap
    # "Strategy A fails at retrieval 60% of the time"
    # "Strategy C fails at LLM 20% of the time"
    for strategy_summary in summary:
        pipeline = strategy_summary["pipeline_name"]

        failure_counts = (
            db.query(
                Metric.failure_source,
                func.count(Metric.id).label("count")
            )
            .join(Run, Run.id == Metric.run_id)
            .filter(Run.pipeline_name == pipeline)
            .group_by(Metric.failure_source)
            .all()
        )

        strategy_summary["failure_distribution"] = {
            row.failure_source.value: row.count
            for row in failure_counts
            if row.failure_source
        }

    return sanitize_json_value({
        "summary": summary,
        "categories_available": [
            row[0]
            for row in (
                db.query(Run.category)
                .distinct()
                .filter(Run.category.isnot(None))
                .all()
            )
        ]
    })


@app.get("/health")
def health_check():
    database_connected = check_database_connection()
    return {
        "status": "ok" if database_connected else "degraded",
        "database": "connected" if database_connected else "disconnected"
    }


# ── Endpoint 5: GET /benchmark/status ────────────────────────────

@app.get("/benchmark/status")
def get_benchmark_status():
    """
    Returns live progress of the benchmark runner.

    Reads benchmark_progress.json written by benchmark_runner.py.
    Frontend polls this every 10 seconds while benchmark is running
    to show a live progress bar.

    Why read from file not database:
    The benchmark runner is a separate process from FastAPI.
    Sharing state via a file is simpler and more reliable than
    a shared in-memory counter across processes.
    """
    testset_path  = Path(config.BENCHMARK_TESTSET_PATH)
    progress_path = BENCHMARK_PROGRESS_PATH
    results_path  = BENCHMARK_RESULTS_PATH

    # Load total question count from testset
    total = 0
    if testset_path.exists():
        with open(testset_path) as f:
            testset = json.load(f)
        total = len(testset)

    # Load completed count from progress file
    completed = 0
    if progress_path.exists():
        with open(progress_path) as f:
            progress = json.load(f)
        completed = len(progress.get("completed_ids", []))

    # Check if results file exists (benchmark done at least once)
    has_results = results_path.exists()

    return {
        "total":       total,
        "completed":   completed,
        "remaining":   max(0, total - completed),
        "percent":     round((completed / total * 100), 1) if total > 0 else 0,
        "is_running":  0 < completed < total,
        "is_complete": completed >= total and total > 0,
        "has_results": has_results,
        # Expected runs = questions × 3 strategies
        "expected_db_runs": completed * 3,
    }


@app.get("/benchmark/results")
def get_benchmark_results(
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
):
    results = load_benchmark_results_file()

    if category:
        results = [
            item for item in results
            if item.get("category") == category
        ]

    if source:
        results = [
            item for item in results
            if item.get("source") == source
        ]

    if search:
        needle = search.strip().lower()
        if needle:
            results = [
                item for item in results
                if needle in (item.get("question") or "").lower()
            ]

    limited_results = results[:limit]

    return {
        "results": limited_results,
        "total": len(results),
        "limit": limit,
        "returned": len(limited_results),
    }


@app.get("/benchmark/summary")
def get_benchmark_summary():
    results = load_benchmark_results_file()
    return build_benchmark_summary(results)
'''

---

## Progress card — save this
```
MEDRAG EVAL — PROGRESS CARD v8

Completed:
✓ config.py
✓ fetcher.py (ChatDoctor + PubMedQA)
✓ indexer.py (3 chunking strategies)
✓ strategy_a/b/c.py (3 pipelines)
✓ db/models.py + db/session.py
✓ ragas_runner.py
✓ deepeval_runner.py
✓ trulens_runner.py
✓ main.py (4 endpoints)

Next:
→ React frontend (4 pages)
→ docker-compose.yml
→ End-to-end testing

Backend is complete. All logic written.
Next session: start React frontend.

Key endpoint decisions:
- Sequential pipeline execution (rate limit safety)
- Atomic DB writes (4 tables in one transaction)
- func.avg in PostgreSQL not Python (performance)
- failure_distribution added to heatmap (diagnostic depth)
- 404/400 explicit error handling on /runs/{run_id}

'''