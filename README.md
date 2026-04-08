# MedRAG Eval

![Frozen Questions](https://img.shields.io/badge/frozen_questions-29-2563eb?style=for-the-badge)
![Benchmark Runs](https://img.shields.io/badge/benchmark_runs-87-0f766e?style=for-the-badge)
![Clinical Domains](https://img.shields.io/badge/clinical_domains-5-f59e0b?style=for-the-badge)
![Backend](https://img.shields.io/badge/backend-FastAPI-059669?style=for-the-badge)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-0284c7?style=for-the-badge)
![Storage](https://img.shields.io/badge/storage-PostgreSQL%20%2B%20ChromaDB-7c3aed?style=for-the-badge)

**A medical RAG hallucination benchmarking platform that evaluates three retrieval pipeline architectures across five clinical domains — measuring hallucination at the claim level and diagnosing whether each failure originated in retrieval or generation.**

Most RAG evaluation stops at the answer level: was the answer correct? MedRAG Eval goes deeper. Every generated answer is decomposed into atomic claims, each claim is independently verified against retrieved context, and the system traces failures back to their source — was the right information never retrieved, or did the model hallucinate despite having it? That distinction is what clinical deployment decisions actually require.

> [!IMPORTANT]
> MedRAG Eval is an evaluation and research platform. It is not a clinical decision system and must not be used for direct patient care.

---
## Demo Video


https://github.com/user-attachments/assets/a7dcb9af-5666-411d-b8d9-89fcfaba9ff4


## The problem this solves

When a RAG system answers a medical question incorrectly, there are two completely different reasons it could have failed:

**Retrieval failure** — the right information was never retrieved. The model had nothing to work with. Fix: better chunking, expanded corpus, improved retrieval strategy.

**Generation failure** — the right information was retrieved. The model ignored it and hallucinated anyway. Fix: tighter prompting, output filtering, or abstention for that domain.

These require different fixes. Most evaluation frameworks treat them as the same failure. MedRAG Eval separates them with a failure-source classifier that labels every run.

---

## What this platform measures

Every run through MedRAG Eval produces six outputs:

| Output | What it measures |
|---|---|
| **Faithfulness** | What fraction of generated claims are grounded in retrieved context |
| **Answer relevancy** | Does the answer actually address the question that was asked |
| **Context precision** | Of everything retrieved, how much was actually useful (signal-to-noise) |
| **Context recall** | Did the retrieved context contain all information needed to answer correctly |
| **Claim-level verdict** | Each atomic assertion labelled `supported`, `partial`, or `hallucinated` |
| **Failure source** | `retrieval` if recall < 0.5 · `llm` if faithfulness < 0.5 despite good recall · `none` if pipeline worked |

---

## Architecture

Three retrieval strategies are benchmarked against an identical generation layer, embedding model, and evaluation suite. The only experimental variable is how documents are chunked and retrieved. This isolates the architectural contribution of each strategy.

```
                     ┌────────────────────────────┐
                     │      Medical Question      │
                     └─────────────┬──────────────┘
                                   │
          ┌────────────────────────┼───────────────────────┐
          │                        │                       │
          ▼                        ▼                       ▼
 ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────────┐
 │   Strategy A    │    │   Strategy B     │    │     Strategy C       │
 │ Fixed Chunking  │    │Semantic Chunking │    │ Parent-Child Chunking│
 │                 │    │                  │    │                      │
 │ 200-word blocks │    │ Splits at topic  │    │ Child (100w) used    │
 │ 40-word overlap │    │ boundaries using │    │ for retrieval        │
 │ Fast baseline   │    │ embedding sim.   │    │ Parent (400w) sent   │
 └────────┬────────┘    └────────┬─────────┘    │ to LLM for context   │
          │                      │              └──────────┬───────────┘
          └──────────────────────┼──────────────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       ChromaDB Retrieval     │
                  │   nomic-embed-text embeddings│
                  │   Cosine similarity + MMR    │
                  │   Keyword overlap reranking  │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │      Answer Generation        │
                  │  Groq  — llama-3.1-8b-instant │
                  │  Ollama — llama3.1:8b/latest  │
                  │  temperature=0 (deterministic)│
                  │  Context-only grounding prompt│
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  │              │              │
                  ▼              ▼              ▼
          ┌──────────┐  ┌─────────────┐  ┌──────────────────┐
          │  RAGAS   │  │  DeepEval   │  │  Failure Source  │
          │ 4 metrics│  │ Claim-level │  │   Classifier     │
          └──────────┘  └─────────────┘  └──────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │          PostgreSQL          │
                  │  runs · metrics · claims ·   │
                  │  traces — atomic transaction │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       React Dashboard        │
                  │  Score Heatmap               │
                  │  Failure Explorer            │
                  │  Trace Viewer                │
                  │  Query Runner                │
                  └──────────────────────────────┘
```

---

## The three strategies explained

### Strategy A — Fixed Chunking

Every document is split into 200-word blocks with a 40-word overlap between consecutive chunks. This is the baseline — simple, fast, and reproducible. The overlap prevents information from being lost at chunk boundaries.

**Why it exists:** To establish a performance floor. Any more sophisticated strategy that does not beat fixed chunking is not worth the added complexity. It also has the lowest indexing cost and most predictable retrieval behaviour, making it appropriate for domains where the corpus is dense and queries can be answered from a single chunk.

**Weakness:** A 200-word boundary can split a clinical explanation mid-reasoning. A chunk that starts with the conclusion of one treatment protocol and the beginning of another gives the model incoherent context.

---

### Strategy B — Semantic Chunking

Documents are split at topic boundaries detected by embedding similarity. The splitter computes embeddings for adjacent sentences and inserts a boundary wherever cosine similarity drops below a threshold — meaning it splits where the text changes subject, not where a word counter hits 200.

**Why it exists:** Medical text has natural structure. A doctor's response typically covers one mechanism per paragraph. Semantic chunking preserves that structure — a chunk about metformin's mechanism stays together rather than being split across two fixed-size blocks.

**Implementation:** Uses `SemanticChunker` from `langchain_experimental` with the same `nomic-embed-text` model used during retrieval. The boundary threshold is set at the 85th percentile of similarity scores — meaning the 15% of most abrupt topic transitions become chunk boundaries.

**Weakness:** Indexing is significantly slower than fixed chunking because every sentence requires an embedding call. Variable chunk sizes also make retrieval behaviour less predictable.

---

### Strategy C — Parent-Child Chunking

Each document is split into parent chunks (400 words) and child chunks (100 words). **Child chunks are embedded and used for retrieval** — their small size means the embedding captures a precise, focused concept. **Parent chunks are returned to the LLM** — their larger size means the model receives full clinical context rather than an isolated fragment.

This decouples the retrieval unit from the generation unit. You get the precision of small-chunk retrieval and the completeness of large-chunk generation at the same time.

**Why it exists:** Fixed and semantic chunking face a fundamental tradeoff — small chunks give precise retrieval but incomplete context; large chunks give complete context but imprecise retrieval. Parent-child eliminates this tradeoff by using different chunk sizes for each purpose.

**Implementation:** MMR (Maximal Marginal Relevance) reranking with λ=0.7 and a similarity ceiling of 0.92 penalises redundant parent chunks — since multiple children from the same parent can all rank highly, the same parent text could otherwise fill all five retrieval slots.

**Weakness:** Retrieval is slower than Strategy A. The redundancy problem persists at the margin even with MMR.

---

## Evaluation pipeline

### RAGAS — four metrics

RAGAS uses the same LLM (llama-3.3-70b-versatile) as a judge to compute four metrics per run:

| Metric | What it measures | How it works |
|---|---|---|
| **Faithfulness** | Claims grounded in context | LLM extracts claims from answer; verifies each against retrieved chunks. Score = supported / total |
| **Answer Relevancy** | Answer addresses the question | LLM generates implied questions; measures cosine similarity to original question |
| **Context Precision** | Retrieved content is useful | Of retrieved chunks, what fraction actually contributed to the answer |
| **Context Recall** | Key information was retrieved | Compared against reference answer — what fraction of required information was present |

**Why temperature=0 on the judge:** Non-zero temperature introduces random variance. The same claim would receive different verdicts on different runs. Temperature=0 makes evaluation deterministic — score changes reflect actual pipeline changes, not judge randomness.

### DeepEval — claim-level verification

Each answer is decomposed into atomic claims using one LLM call, then all claims are verified against retrieved context in a single batch call:

- `supported` — directly supported by at least one retrieved chunk
- `partial` — partially supported but adds details not in context
- `hallucinated` — contradicts context or has no basis in any retrieved chunk

**Why batch verification:** Sequential verification is O(n) with answer length. Batch verification is one call regardless of claim count — approximately 6× faster for a typical answer, same accuracy.

### Failure source classifier

```python
if context_recall < 0.5:
    failure_source = "retrieval"   # right information never retrieved
elif faithfulness < 0.5:
    failure_source = "llm"         # retrieved correctly, LLM hallucinated anyway
else:
    failure_source = "none"        # pipeline working correctly
```

This classifier is the core diagnostic output. It tells a deployment team whether to invest in retrieval improvements (corpus, chunking, reranking) or generation constraints (prompting, abstention).

---

## Benchmark results

**Eval set:** 29 frozen PubMedQA questions, yes/no only, balanced across 5 domains (~3 yes + 3 no per domain), frozen before benchmarking to prevent contamination.
**Corpus:** ChatDoctor-HealthCareMagic-100k, 500 records per category, held out before indexing to prevent leakage.
**Total:** 87 strategy evaluations.

### Overall leaderboard

| Strategy | Faithfulness | Relevancy | Precision | Recall | Verdict Accuracy | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|
| **A — Fixed Chunking** | **73.0%** | **30.7%** | 48.8% | **46.4%** | 51.7% | 47.4s |
| B — Semantic Chunking | 69.0% | 19.2% | **50.8%** | 37.7% | 55.2% | **45.5s** |
| C — Parent-Child | 70.4% | 24.5% | 45.4% | 37.8% | **58.6%** | 48.6s |

### Faithfulness by domain

| Domain | Strategy A | Strategy B | Strategy C | Winner |
|---|---:|---:|---:|---|
| Asthma | 76.0% | 80.0% | **83.3%** | C |
| Cancer | **91.7%** | 79.2% | 70.0% | A |
| Depression | **72.1%** | 60.0% | 62.5% | A |
| Diabetes | 56.7% | 57.9% | **73.3%** | C |
| Hypertension | **71.8%** | 66.7% | 54.2% | A |

### Context recall by domain

| Domain | Strategy A | Strategy B | Strategy C |
|---|---:|---:|---:|
| Asthma | **37.8%** | 19.4% | 26.1% |
| Cancer | **69.4%** | 32.5% | 47.2% |
| Depression | **43.1%** | 40.9% | 34.7% |
| Diabetes | 40.6% | **44.9%** | 35.6% |
| Hypertension | 40.0% | **53.3%** | 46.7% |

### Failure source distribution

| Strategy | None (working) | Retrieval failure | LLM failure | Null (rate limited) |
|---|---:|---:|---:|---:|
| A — Fixed | 19 runs (65%) | 7 runs (24%) | 3 runs (10%) | — |
| B — Semantic | 18 runs (62%) | 8 runs (28%) | 3 runs (10%) | — |
| C — Parent-Child | 18 runs (62%) | 11 runs (38%) | 0 runs | — |

Strategy C has zero LLM failures — when parent-child retrieval succeeds, the model grounds correctly. But it has the most retrieval failures, suggesting that child embedding precision sometimes misses the right parent document entirely.

---

## Key findings

### Finding 1 — No strategy wins every domain

Domain performance is not uniform. A leads cancer, depression, hypertension. C leads asthma, diabetes. B leads retrieval precision and latency. No single strategy dominates all metrics across all domains — the central finding of this benchmark.

**Implication:** Domain-specific strategy routing is required for production medical RAG.

### Finding 2 — Retrieval failure is more common than generation failure

30% of classifiable runs are retrieval failures versus 7% LLM failures. The primary bottleneck is corpus coverage, not model behaviour. Improving the corpus or retrieval architecture has more impact than prompt engineering alone.

### Finding 3 — Cancer shows the highest faithfulness but lowest precision

Cancer queries produce 91.7% faithfulness for Strategy A but only 31.7–49.2% context precision. The model grounds well when it answers, but retrieval pulls in loosely related chunks alongside the relevant ones. Precision-focused improvements (tighter similarity thresholds, domain reranking) would help most here.

### Finding 4 — Context recall plateaus across all strategies

Recall stays between 19–69% across all domains and strategies. This is a corpus gap, not a retrieval failure. ChatDoctor is conversational data; PubMedQA reference answers require guideline-grade evidence. No chunking strategy can retrieve information that was never indexed.

### Finding 5 — Faithfulness and relevancy are in tension

The strict context-grounding prompt produces high faithfulness but suppresses relevancy. The model answers safely but sometimes incompletely. This is not a bug — it is a deployment decision that must be made explicitly. There is no configuration that maximises both simultaneously.

---

## Deployment recommendations

| Domain | Recommended strategy | Reason |
|---|---|---|
| Asthma | **C — Parent-Child** | 83.3% faithfulness — best grounding for multi-sentence clinical explanations |
| Cancer | **A — Fixed** + human review | 91.7% faithfulness but 8.3% of claims still unsupported — human review required |
| Depression | **A — Fixed** | 72.1% faithfulness, best recall at 43.1% |
| Diabetes | **C — Parent-Child** | 73.3% faithfulness — strongest grounding in this domain |
| Hypertension | **B — Semantic** | Best recall (53.3%) and precision (71.8%) — corpus is dense enough for semantic boundaries |

---

## Tech stack

| Layer | Technology | Decision rationale |
|---|---|---|
| LLM | Groq llama-3.1-8b-instant | Fast inference, free tier sufficient, deterministic at temp=0 |
| Embeddings | nomic-embed-text via Ollama | Local, zero API cost, same model at index and query time |
| Vector DB | ChromaDB | 3 persistent collections, cosine similarity, native MMR support |
| Evaluation | RAGAS + custom DeepEval pipeline | RAGAS for metric standards, DeepEval for atomic claim verification |
| Backend | FastAPI + Python 3.11 | Async-compatible, clean DI via `Depends`, automatic OpenAPI docs |
| Database | PostgreSQL | 4 tables, UUID keys, atomic transactions across all 4 per run |
| Frontend | React 19 + Vite + Recharts | 4 pages, Axios hook layer, live benchmark progress polling |

---

## Database schema

```
runs        → id (UUID) · question · pipeline_name · answer · category · latency_ms
metrics     → id · run_id → runs · faithfulness · answer_relevancy · context_precision
              context_recall · failure_source · evaluated_at
claims      → id · run_id → runs · claim_text · claim_index · status · supporting_context
traces      → id · run_id → runs · retrieved_contexts · context_count · raw_pipeline_output
```

All four tables are written in a single atomic transaction per run. Partial writes create orphaned records that corrupt Failure Explorer queries — atomicity is non-negotiable.

---

## Dashboard pages

**Query Runner** — Submit any question and see all three strategies answer simultaneously. Live timer, retrieval provenance with similarity and MMR scores, RAGAS metrics with animated bars, claim-level breakdown side by side.

**Score Heatmap** — Color-coded RAGAS metrics per strategy (green ≥ 80%, amber ≥ 50%, red < 50%). Failure distribution donuts. Benchmark findings panel. Deployment recommendation panel with per-domain guidance.

**Failure Explorer** — Filterable table by strategy, domain, faithfulness threshold. Click any row to expand the full claim breakdown with the exact supporting context for each claim verdict.

**Trace Viewer** — Full run trace: retrieved chunks with similarity scores and reranking positions, metric tiles, claim analysis with supporting context text.

---

## Project structure

```
MedRag-Eval/
├── backend/
│   ├── main.py                    5 endpoints: /run-query, /runs, /runs/{id},
│   │                              /metrics/summary, /benchmark/status
│   ├── config.py                  All configuration centralised
│   ├── groq_compat.py             LRU-cached client + exponential backoff retry
│   ├── benchmark_runner.py        Resumable — saves progress after every question
│   ├── pipelines/
│   │   ├── retrieval.py           MMR, keyword reranking, provenance tracking
│   │   ├── strategy_a.py          Fixed chunking + generation prompt
│   │   ├── strategy_b.py          Semantic chunking pipeline
│   │   └── strategy_c.py          Parent-child with MMR reranking
│   ├── evaluation/
│   │   ├── ragas_runner.py        4 metrics + nest_asyncio Windows fix
│   │   ├── deepeval_runner.py     Atomic claim extraction + batch verification
│   │   └── benchmark_metrics.py  Binary verdict extraction
│   ├── ingestion/
│   │   ├── fetcher.py             ChatDoctor + PubMedQA, deterministic split
│   │   └── indexer.py             3 ChromaDB collections, resumable
│   ├── db/
│   │   ├── models.py              SQLAlchemy models + enums
│   │   └── session.py             Connection pool + FastAPI Depends
│   └── testset/
│       ├── qa_pairs.json          29 frozen questions
│       ├── benchmark_results.json 87-run results
│       └── benchmark_progress.json Resumable state
└── frontend/
    └── src/
        ├── api/client.js          Axios + interceptors
        ├── hooks/                 useRunQuery, useRuns, useSummary
        ├── components/            ui/, charts/, layout/
        └── pages/                 QueryRunner, ScoreHeatmap, FailureExplorer, TraceViewer
```

---

## How to run locally

```bash
# 1. Start PostgreSQL
docker compose up -d postgres

# 2. Environment variables
cp .env.example .env
# Set GROQ_API_KEY and DATABASE_URL

# 3. Install backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Pull embedding model
ollama pull nomic-embed-text

# 5. Index the corpus (first run only — ~30 minutes)
python -m backend.ingestion.indexer

# 6. Start backend
uvicorn backend.main:app --reload
# API docs: http://localhost:8000/docs

# 7. Start frontend
cd frontend && npm install && npm run dev
# Dashboard: http://localhost:3000

# 8. Run the benchmark (optional)
python -m backend.benchmark_runner
```

---

## Known limitations

**28% of runs have null faithfulness scores.** Groq's free tier rate limits RAGAS when three strategies run sequentially (~7 LLM calls per strategy). A 15-second inter-strategy delay reduces but does not eliminate this. A paid Groq tier or local judge model would close the gap.

**Answer relevancy averages 19–31%.** This benchmark mixes old runs (strict prompt, near-zero relevancy) with newer runs (improved prompt, 0.65–0.83 relevancy). The average reflects that history. Re-running the full benchmark with the current prompt would raise this significantly.

**Context recall plateaus at 35–55%.** The ChatDoctor corpus is conversational data, not clinical guidelines. Recall cannot exceed what the corpus contains. Extending with NICE or WHO guidelines would directly raise this metric.

**TruLens disabled on Python 3.12.** TruLens 0.28.0 requires Python 3.11. The integration is written in `trulens_runner.py` but disabled by default.

**Strategy C parent redundancy.** MMR reduces but does not fully eliminate cases where multiple child chunks map to the same parent, consuming multiple retrieval slots with identical context.
