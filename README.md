# MedRAG Eval

![Frozen Questions](https://img.shields.io/badge/frozen_questions-29-2563eb?style=for-the-badge)
![Benchmark Runs](https://img.shields.io/badge/benchmark_runs-87-0f766e?style=for-the-badge)
![Clinical Domains](https://img.shields.io/badge/clinical_domains-5-f59e0b?style=for-the-badge)
![Backend](https://img.shields.io/badge/backend-FastAPI-059669?style=for-the-badge)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-0284c7?style=for-the-badge)
![Storage](https://img.shields.io/badge/storage-PostgreSQL%20%2B%20Chroma-7c3aed?style=for-the-badge)

Medical RAG evaluation platform for benchmarking hallucination risk across multiple retrieval strategies. Instead of stopping at answer-level correctness, MedRAG Eval breaks a response into claims, checks whether those claims are grounded in retrieved context, and surfaces whether a bad result came from retrieval or generation.

> [!IMPORTANT]
> This project is built for RAG benchmarking, debugging, and research workflows. It is not a clinical decision system and should not be used for direct patient care without human review.

## Why this exists

Most RAG demos report one score and call it evaluation. That is not enough for medical QA.

MedRAG Eval is designed to answer the questions teams actually need during deployment:

- Did the system retrieve the right evidence?
- Did the model stay grounded in that evidence?
- Which chunking strategy is safer for a given domain?
- When a run fails, is the problem corpus coverage, retrieval quality, or generation drift?

## What the product includes

| Surface | What it does |
| --- | --- |
| `Query Runner` | Runs the same question through all 3 strategies side by side. |
| `Benchmark Results` | Reads the frozen benchmark JSON and shows per-question, per-strategy outputs. |
| `Score Heatmap` | Compares average faithfulness, relevancy, precision, recall, latency, and failure distribution. |
| `Failure Explorer` | Filters low-faithfulness runs and inspects claim-level hallucinations. |
| `Trace Viewer` | Shows retrieval provenance, metric breakdown, and claim support for a single run. |

## Benchmark snapshot

The snapshot below is taken from the checked-in file [`backend/testset/benchmark_results.json`](backend/testset/benchmark_results.json), not from placeholder copy.

| Snapshot | Value |
| --- | --- |
| Eval set | 29 frozen PubMedQA questions |
| Total runs | 87 strategy evaluations |
| Domains | asthma, cancer, depression, diabetes, hypertension |
| Retrieval corpus | ChatDoctor-HealthCareMagic-100k |
| Indexed size | 500 records per category |
| Strategies | fixed chunking, semantic chunking, parent-child chunking |

### Strategy leaderboard

| Strategy | Primary strength | Accuracy | Faithfulness | Relevancy | Precision | Recall | Avg latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A - Fixed Chunking` | Best grounding | 51.7% | **73.0%** | **30.7%** | 48.8% | **46.4%** | 47.4s |
| `B - Semantic Chunking` | Fastest + best retrieval precision | 55.2% | 69.0% | 19.2% | **50.8%** | 37.7% | **45.5s** |
| `C - Parent-Child Chunking` | Best verdict accuracy | **58.6%** | 70.4% | 24.5% | 45.4% | 37.8% | 48.6s |

### What the current benchmark says

- Strategy C currently has the highest answer-level accuracy across the frozen benchmark.
- Strategy A produces the strongest average grounding and the best average recall.
- Strategy B is the fastest strategy in the shipped benchmark and has the highest retrieval precision.
- No single strategy dominates every metric, which is exactly why the dashboard compares tradeoffs instead of declaring one universal winner.

### Domain view

| Domain | Strongest current strategy | Reading of the result |
| --- | --- | --- |
| Asthma | `B - Semantic` | Ties best accuracy and edges out the others on faithfulness. |
| Diabetes | `C - Parent-Child` | Ties best accuracy and has the strongest grounding. |
| Hypertension | `B - Semantic` | Best accuracy with the strongest recall in this domain. |
| Depression | `C - Parent-Child` | Ties best accuracy and slightly leads on faithfulness. |
| Cancer | No clearly safe winner | Best accuracy is still only 50.0 percent, so this domain still needs human review. |

## What makes the evaluation different

### 1. Claim-level checking

Each generated answer is decomposed into atomic claims and scored against retrieved context. That catches failures that answer-level grading can miss.

### 2. Failure-source diagnosis

Runs are labeled with an operational failure source:

```python
if context_recall < 0.5:
    failure_source = "retrieval"
elif faithfulness < 0.5:
    failure_source = "llm"
else:
    failure_source = "none"
```

This lets you see whether to improve chunking, expand the corpus, or tighten generation behavior.

### 3. Same question, same eval stack, three retrieval strategies

All strategies share the same benchmark set and evaluation flow. The core difference is retrieval architecture:

- `Strategy A`: fixed 200-word chunks with overlap
- `Strategy B`: semantic boundary-aware chunks
- `Strategy C`: child chunks for retrieval, parent chunks for generation

## System architecture

```text
Question
  -> Strategy A / B / C retrieval
  -> grounded answer generation
  -> RAGAS metrics
  -> DeepEval claim verification
  -> failure-source diagnosis
  -> PostgreSQL + file-backed benchmark outputs
  -> React dashboard + FastAPI endpoints
```

## Tech stack

| Layer | Technology |
| --- | --- |
| API | FastAPI |
| Frontend | React 19 + Vite + Recharts |
| Database | PostgreSQL |
| Vector store | ChromaDB |
| Embeddings | Ollama `nomic-embed-text` |
| LLM access | Local Ollama by default, Groq supported through compatibility layer |
| Evaluation | RAGAS + custom DeepEval claim pipeline |

## Run locally

### Prerequisites

- Python 3.11 recommended
- Node.js 18 or newer
- Docker Desktop or a local PostgreSQL instance
- Ollama

### 1. Start PostgreSQL

```bash
docker compose up -d postgres
```

The included `docker-compose.yml` starts PostgreSQL on `localhost:5432` with database name `medrag`.

### 2. Create your environment file

Copy [`.env.example`](.env.example) to `.env` and update values if needed.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

### 3. Install Ollama models

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:latest
```

### 4. Install backend dependencies

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. Build the vector indexes

```bash
python -m backend.ingestion.indexer
```

This creates the three Chroma collections used by the benchmarked pipelines.

### 7. Start the backend

```bash
uvicorn backend.main:app --reload
```

Backend API docs: `http://127.0.0.1:8000/docs`

### 8. Start the frontend

In a new terminal:

```bash
cd frontend
npm run dev
```

Dashboard: `http://127.0.0.1:3000`

## Run the frozen benchmark

Once the backend is running, execute:

```bash
python -m backend.benchmark_runner
```

Artifacts written by the runner:

- [`backend/testset/qa_pairs.json`](backend/testset/qa_pairs.json): frozen benchmark questions
- [`backend/testset/benchmark_progress.json`](backend/testset/benchmark_progress.json): resumable progress state
- [`backend/testset/benchmark_results.json`](backend/testset/benchmark_results.json): per-question benchmark output

## Optional data regeneration

If you want to rebuild the evaluation sets instead of using the shipped files:

```bash
python -m backend.ingestion.fetcher
```

## Repository layout

```text
backend/
  main.py                  FastAPI endpoints for query, history, traces, and benchmark summaries
  benchmark_runner.py      Resumable benchmark runner for the frozen test set
  ingestion/fetcher.py     Dataset loading and frozen eval-set generation
  ingestion/indexer.py     Chroma indexing for all three strategies
  pipelines/               Retrieval and generation logic
  evaluation/              RAGAS and claim-level evaluation code
  db/                      SQLAlchemy models and session management

frontend/
  src/pages/               Query Runner, Benchmark Results, Score Heatmap, Failure Explorer, Trace Viewer
  src/components/          Shared UI, charts, layout, and metric cells
```

## Known limitations

- The shipped benchmark is still small. It is good for comparative debugging, not for broad clinical claims.
- The retrieval corpus is conversational medical data, not guideline-grade evidence.
- Provider choice matters. The codebase supports both local Ollama and Groq-backed workflows, so scores can move when model settings change.
- Some benchmark runs may not receive a failure label when upstream metrics are unavailable.

## Practical use cases

- Compare chunking strategies before deploying a medical RAG assistant.
- Debug whether a failure came from retrieval coverage or model generation.
- Build a dashboard-friendly benchmark artifact that non-ML stakeholders can review.
- Create a repeatable local workflow for RAG benchmarking without custom observability tooling from scratch.
