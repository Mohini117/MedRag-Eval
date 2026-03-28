# backend/benchmark_runner.py
#
# Runs the full frozen PubMedQA eval testset through all 3 RAG strategies.
# Calls the existing /run-query FastAPI endpoint for each question.
#
# Why call the HTTP endpoint instead of importing functions directly:
# The endpoint handles the full pipeline — TruLens tracing, RAGAS eval,
# DeepEval claims, PostgreSQL persistence — all in one atomic transaction.
# Duplicating that logic here would create drift. Reusing the endpoint
# guarantees benchmark results are identical to manual runs.
#
# Usage:
#   Make sure FastAPI is running:  uvicorn backend.main:app --reload
#   Then in a NEW terminal:        python -m backend.benchmark_runner
#
# Resume behaviour:
#   Progress is saved to backend/testset/benchmark_progress.json after
#   every completed question. If the script is interrupted, re-running it
#   will skip already-completed questions and continue from where it stopped.

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from backend.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────
API_BASE          = "http://127.0.0.1:8000"
TESTSET_PATH      = Path(config.BENCHMARK_TESTSET_PATH)
PROGRESS_PATH     = Path("backend/testset/benchmark_progress.json")
RESULTS_PATH      = Path("backend/testset/benchmark_results.json")

# Delay between each question to avoid Groq rate limits.
# A single benchmark question triggers multiple judge/model calls even when
# strategies run sequentially, so this needs to be materially higher than
# a simple "3 strategies = 3 requests" estimate.
DELAY_BETWEEN_QUESTIONS = 30  # seconds
DELAY_BETWEEN_RETRIES   = 45  # seconds — longer pause on rate limit error

MAX_RETRIES = 1 # retries per question before giving up


# ── Load testset ──────────────────────────────────────────────────

def load_testset() -> list[dict]:
    if not TESTSET_PATH.exists():
        raise FileNotFoundError(
            f"Testset not found at {TESTSET_PATH}. "
            "Run: python -m backend.ingestion.fetcher"
        )
    with open(TESTSET_PATH) as f:
        testset = json.load(f)
    sources = sorted({item.get("source", "unknown") for item in testset})
    logger.info(
        "Loaded %s questions from %s | sources=%s",
        len(testset),
        TESTSET_PATH,
        ", ".join(sources),
    )
    return testset


# ── Progress tracking ─────────────────────────────────────────────
# We track completed questions by their id field.
# This means re-running the script safely skips already-done questions.

def load_progress() -> set:
    if not PROGRESS_PATH.exists():
        return set()
    with open(PROGRESS_PATH) as f:
        data = json.load(f)
    completed = set(data.get("completed_ids", []))
    logger.info(f"Resuming — {len(completed)} questions already completed")
    return completed


def save_progress(completed_ids: set, results: list) -> None:
    with open(PROGRESS_PATH, "w") as f:
        json.dump({"completed_ids": list(completed_ids)}, f)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


# ── API health check ──────────────────────────────────────────────

def check_api_alive() -> bool:
    try:
        r = requests.get(f"{API_BASE}/docs", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ── Run a single question through the API ─────────────────────────

def run_question(question: dict) -> dict | None:
    """
    POST /run-query with one PubMedQA question.
    No timeout — waits as long as it takes for the pipeline to finish.
    Only moves to next question after this one fully completes.
    """
    payload = {
        "question":         question["question"],
        "reference_answer": question["reference_answer"],
        "category":         question["category"],
        "final_answer":     question.get("final_answer"),
        "source":           question.get("source"),
        "enable_trulens":   False,
        "enable_deepeval":  False,
        "enable_ragas":     True,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"  POST /run-query — attempt {attempt}/{MAX_RETRIES} (no timeout — waiting for completion)"
            )
            response = requests.post(
                f"{API_BASE}/run-query",
                json=payload,
                timeout=None,  # wait forever — let the pipeline finish naturally
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                logger.warning(
                    f"  Rate limited (429) — waiting {DELAY_BETWEEN_RETRIES}s"
                )
                time.sleep(DELAY_BETWEEN_RETRIES)
                continue

            logger.error(
                f"  HTTP {response.status_code}: {response.text[:200]}"
            )
            return None

        except requests.exceptions.ConnectionError:
            logger.error(f"  Connection error — is FastAPI running?")
            time.sleep(10)
        except Exception as e:
            logger.error(f"  Error on attempt {attempt}: {str(e)}")
            if attempt < MAX_RETRIES:
                time.sleep(5)

    logger.error(f"  All {MAX_RETRIES} attempts failed — skipping question")
    return None

# ── Summary statistics ────────────────────────────────────────────

def print_summary(results: list) -> None:
    """
    Print a clean benchmark summary after all questions complete.
    Groups results by strategy and computes average metrics.
    """
    from collections import defaultdict

    strategy_metrics = defaultdict(lambda: {
        "faithfulness": [], "answer_relevancy": [],
        "context_precision": [], "context_recall": [],
        "answer_accuracy": [],
        "failure_none": 0, "failure_retrieval": 0, "failure_llm": 0,
        "total": 0
    })

    for result in results:
        for r in result.get("results", []):
            name = r.get("pipeline_name", "unknown")
            m    = r.get("metrics", {})
            sm   = strategy_metrics[name]
            sm["total"] += 1

            for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                v = m.get(key)
                if v is not None:
                    sm[key].append(v)

            verdict_correct = r.get("benchmark_eval", {}).get("is_correct")
            if verdict_correct is not None:
                sm["answer_accuracy"].append(1.0 if verdict_correct else 0.0)

            fs = r.get("failure_source", "none") or "none"
            sm[f"failure_{fs}"] += 1

    print("\n" + "="*70)
    print("  MEDRAG EVAL — BENCHMARK COMPLETE")
    print("="*70)

    for name, sm in strategy_metrics.items():
        short = {
            "strategy_a_fixed_chunking":        "Strategy A · Fixed Chunking",
            "strategy_b_semantic_chunking":     "Strategy B · Semantic Chunking",
            "strategy_c_parent_child_chunking": "Strategy C · Parent-Child",
        }.get(name, name)

        def avg(lst): return f"{sum(lst)/len(lst)*100:.1f}%" if lst else "—"

        print(f"\n  {short}")
        print(f"  {'─'*50}")
        print(f"  Runs:               {sm['total']}")
        print(f"  Faithfulness:       {avg(sm['faithfulness'])}")
        print(f"  Answer Relevancy:   {avg(sm['answer_relevancy'])}")
        print(f"  Context Precision:  {avg(sm['context_precision'])}")
        print(f"  Context Recall:     {avg(sm['context_recall'])}")
        print(f"  Verdict Accuracy:   {avg(sm['answer_accuracy'])}")
        print(f"  Failure — None:     {sm['failure_none']}")
        print(f"  Failure — Retrieval:{sm['failure_retrieval']}")
        print(f"  Failure — LLM:      {sm['failure_llm']}")

    print("\n" + "="*70)
    print(f"  Results saved to: {RESULTS_PATH}")
    print("="*70 + "\n")


# ── Main entry point ──────────────────────────────────────────────

def run_benchmark() -> None:
    logger.info("="*60)
    logger.info("  MedRAG Eval — Full Benchmark Runner")
    logger.info("="*60)

    # 1. Check API is live
    logger.info("Checking FastAPI is running...")
    if not check_api_alive():
        logger.error(
            "FastAPI is not running at http://127.0.0.1:8000\n"
            "Start it first:  uvicorn backend.main:app --reload\n"
            "Then re-run this script in a separate terminal."
        )
        return

    logger.info("API is live ✓")

    # 2. Load testset
    testset = load_testset()

    # 3. Load progress — skip already completed questions
    completed_ids = load_progress()
    remaining     = [q for q in testset if q["id"] not in completed_ids]

    total     = len(testset)
    remaining_count = len(remaining)
    logger.info(
        f"Testset: {total} questions total | "
        f"{total - remaining_count} already done | "
        f"{remaining_count} remaining"
    )

    if remaining_count == 0:
        logger.info("All questions already completed. Nothing to do.")
        logger.info(f"Results are at: {RESULTS_PATH}")
        return

    # 4. Load existing results
    existing_results = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            existing_results = json.load(f)

    all_results = list(existing_results)

    # 5. Estimate time
    estimated_seconds = remaining_count * 60  # benchmark mode disables extra eval passes
    estimated_minutes = estimated_seconds // 60
    logger.info(
        f"Estimated time: ~{estimated_minutes} minutes "
        f"({remaining_count} questions × ~90s each)"
    )
    logger.info("Progress is saved after every question — safe to interrupt")
    logger.info("─"*60)

    # 6. Run each question
    start_time = time.time()

    for i, question in enumerate(remaining, 1):
        logger.info(
            f"[{i}/{remaining_count}] {question['category'].upper()} | "
            f"{(question.get('final_answer') or 'n/a').upper()} | "
            f"{question['question'][:70]}..."
        )

        result = run_question(question)

        if result is not None:
            # Attach testset metadata to result for analysis
            result["testset_id"]      = question["id"]
            result["category"]        = question["category"]
            result["final_answer"]    = question.get("final_answer")
            result["source"]          = question.get("source")
            result["completed_at"]    = datetime.utcnow().isoformat()

            all_results.append(result)
            completed_ids.add(question["id"])
            save_progress(completed_ids, all_results)

            # Log per-strategy scores immediately
            for r in result.get("results", []):
                name  = r.get("pipeline_name", "?")[-9:]  # last 9 chars
                faith = r.get("metrics", {}).get("faithfulness")
                recall = r.get("metrics", {}).get("context_recall")
                verdict = r.get("benchmark_eval", {}).get("predicted_verdict")
                verdict_ok = r.get("benchmark_eval", {}).get("is_correct")
                fsrc  = r.get("failure_source", "—")
                faith_str  = f"{faith*100:.0f}%" if faith is not None else "—"
                recall_str = f"{recall*100:.0f}%" if recall is not None else "—"
                verdict_str = (
                    f"{verdict} ({'ok' if verdict_ok else 'bad'})"
                    if verdict_ok is not None else
                    (verdict or "n/a")
                )
                logger.info(
                    f"  {name} | faith={faith_str} recall={recall_str} verdict={verdict_str} failure={fsrc}"
                )
        else:
            logger.warning(f"  Skipped — could not get result for question {question['id']}")

        # Respect Groq rate limits between questions
        if i < remaining_count:
            logger.info(f"  Waiting {DELAY_BETWEEN_QUESTIONS}s before next question...")
            time.sleep(DELAY_BETWEEN_QUESTIONS)

    # 7. Final summary
    elapsed = time.time() - start_time
    logger.info(f"Benchmark complete in {elapsed/60:.1f} minutes")
    print_summary(all_results)


if __name__ == "__main__":
    run_benchmark()
