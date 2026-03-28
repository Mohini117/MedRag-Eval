import logging
import sys
import time
from datetime import datetime

from backend.config import config
from backend.pipelines.strategy_a import determine_failure_source


logger = logging.getLogger(__name__)

TRULENS_IMPORT_ERROR = None
TRULENS_ENVIRONMENT_NOTE = None

if sys.version_info >= (3, 12):
    TRULENS_ENVIRONMENT_NOTE = (
        "TruLens 0.28.0 is not compatible with Python 3.12 in this project. "
        "Run the app with Python 3.11 to enable TruLens tracing."
    )

try:
    from trulens_eval import Tru, Feedback, TruBasicApp
    from trulens_eval.feedback.provider import Groq as TruGroq
    from trulens_eval.schema import Record
except Exception as exc:  # pragma: no cover - environment dependent
    Tru = Feedback = TruBasicApp = TruGroq = Record = None
    TRULENS_IMPORT_ERROR = exc


def _require_trulens() -> None:
    if TRULENS_IMPORT_ERROR is not None:
        message = "TruLens is unavailable in this environment."
        if TRULENS_ENVIRONMENT_NOTE:
            message += f" {TRULENS_ENVIRONMENT_NOTE}"
        raise RuntimeError(
            f"{message} "
            f"Original import error: {TRULENS_IMPORT_ERROR}"
        ) from TRULENS_IMPORT_ERROR


def _init_trulens():
    _require_trulens()

    tru = Tru()
    provider = TruGroq(
        api_key=config.GROQ_API_KEY,
        model_engine=config.GENERATION_MODEL,
    )

    f_groundedness = (
        Feedback(
            provider.groundedness_measure_with_cot_reasons,
            name="Groundedness",
        )
        .on_input_output()
    )

    f_context_relevance = (
        Feedback(
            provider.context_relevance_with_cot_reasons,
            name="Context Relevance",
        )
        .on_input()
        .aggregate(min)
    )

    f_answer_relevance = (
        Feedback(
            provider.relevance_with_cot_reasons,
            name="Answer Relevance",
        )
        .on_input_output()
    )

    return tru, [f_groundedness, f_context_relevance, f_answer_relevance]


TRULENS_RUNTIME = None


def _get_runtime():
    global TRULENS_RUNTIME
    if TRULENS_RUNTIME is None:
        tru, feedbacks = _init_trulens()
        from backend.pipelines import strategy_a, strategy_b, strategy_c

        def strategy_a_runner(question: str, category: str | None = None):
            return strategy_a.run(question, category=category)

        def strategy_b_runner(question: str, category: str | None = None):
            return strategy_b.run(question, category=category)

        def strategy_c_runner(question: str, category: str | None = None):
            return strategy_c.run(question, category=category)

        TRULENS_RUNTIME = {
            "tru": tru,
            "pipelines": {
                "strategy_a": TruBasicApp(
                    strategy_a_runner,
                    app_id="strategy_a_fixed_chunking",
                    feedbacks=feedbacks,
                ),
                "strategy_b": TruBasicApp(
                    strategy_b_runner,
                    app_id="strategy_b_semantic_chunking",
                    feedbacks=feedbacks,
                ),
                "strategy_c": TruBasicApp(
                    strategy_c_runner,
                    app_id="strategy_c_parent_child_chunking",
                    feedbacks=feedbacks,
                ),
            },
        }
    return TRULENS_RUNTIME


def run_with_tracing(
    question: str,
    strategy: str,
    run_id: str = None,
    category: str | None = None,
) -> dict:
    runtime = _get_runtime()
    pipelines = runtime["pipelines"]

    if strategy not in pipelines:
        raise ValueError(
            f"Unknown strategy: {strategy}. Must be one of: {list(pipelines.keys())}"
        )

    traced_pipeline = pipelines[strategy]
    logger.info(
        "Running traced pipeline - strategy=%s run_id=%s question='%s...'",
        strategy,
        run_id,
        question[:60],
    )

    start_time = time.time()
    with traced_pipeline as recording:
        result = traced_pipeline.app(question, category)

    record: Record = recording.get()
    trulens_scores = extract_trulens_scores(record)

    logger.info(
        "Traced pipeline complete - strategy=%s groundedness=%s time=%.1fs",
        strategy,
        trulens_scores.get("groundedness"),
        time.time() - start_time,
    )

    result["trulens"] = trulens_scores
    result["trulens"]["trace_id"] = str(record.record_id)
    return result


def extract_trulens_scores(record: Record) -> dict:
    scores = {
        "groundedness": None,
        "context_relevance_min": None,
        "context_relevance_per_chunk": [],
        "answer_relevance": None,
        "raw_feedback": {},
    }

    try:
        for feedback_result in record.feedback_results:
            name = feedback_result.name
            score = feedback_result.result
            scores["raw_feedback"][name] = score

            if name == "Groundedness":
                scores["groundedness"] = float(score)
            elif name == "Context Relevance":
                scores["context_relevance_min"] = float(score)
            elif name == "Answer Relevance":
                scores["answer_relevance"] = float(score)
    except Exception as exc:  # pragma: no cover - defensive extraction
        logger.error("Failed to extract TruLens scores: %s", exc)

    return scores


def build_trace_for_storage(
    result: dict,
    ragas_metrics: dict,
    run_id: str,
) -> dict:
    faithfulness = ragas_metrics.get("faithfulness")
    context_recall = ragas_metrics.get("context_recall")
    failure_source = None

    if faithfulness is not None and context_recall is not None:
        failure_source = determine_failure_source(
            context_recall=context_recall,
            faithfulness=faithfulness,
        )

    trulens_data = result.get("trulens", {})

    return {
        "run_id": run_id,
        "retrieved_contexts": result.get("contexts", []),
        "context_count": len(result.get("contexts", [])),
        "trulens_feedback": str(trulens_data.get("raw_feedback", {})),
        "groundedness_score": trulens_data.get("groundedness"),
        "context_relevance_min": trulens_data.get("context_relevance_min"),
        "answer_relevance": trulens_data.get("answer_relevance"),
        "failure_source": failure_source,
        "trace_id": trulens_data.get("trace_id"),
        "created_at": datetime.utcnow().isoformat(),
    }
