# MedRAG Eval

**A medical RAG hallucination benchmarking platform that evaluates three retrieval pipeline architectures across five clinical domains — measuring hallucination risk at the claim level so teams can make evidence-based deployment decisions.**

Most RAG systems are evaluated with a single accuracy score. MedRAG Eval goes deeper: every LLM answer is decomposed into atomic claims, each claim is verified against retrieved context, and the failure is traced back to its source — retrieval gap or LLM generation error. The result is a diagnostic system, not just a scorecard.

---

## The problem this solves

RAG systems deployed in medical contexts hallucinate silently. A system can retrieve the right documents and still generate incorrect claims. Traditional evaluation catches this only at the answer level — "was the answer correct?" — which tells you nothing about *why* it failed or *where* to fix it.

MedRAG Eval measures at the claim level: each atomic assertion in a generated answer is independently verified against the retrieved context. This surfaces the exact failure mode — whether the retrieval pipeline missed the right information, or whether the LLM ignored correct information and generated something unsupported.

---

## Architecture

Three retrieval strategies are benchmarked against the same generation layer, embedding model, and evaluation suite. The only variable is how documents are chunked and retrieved.

```
Question
    │
    ├── Strategy A: Fixed Chunking
    │       200-word blocks, 40-word overlap
    │       Simple baseline — predictable, fast
    │
    ├── Strategy B: Semantic Chunking
    │       Splits at topic boundaries using embeddings
    │       Coherent chunks — better context quality
    │
    └── Strategy C: Parent-Child Chunking
            Child chunks (100w) embedded for retrieval precision
            Parent chunks (400w) returned to LLM for full context
            Decouples retrieval unit from generation unit
                │
                ▼
        Generation (same for all strategies)
        Groq — llama-3.3-70b-versatile — temperature=0
                │
                ▼
        Evaluation
        ├── RAGAS: faithfulness, answer relevancy,
        │         context precision, context recall
        ├── DeepEval: claim-level hallucination detection
        └── Failure source diagnosis: retrieval vs LLM
                │
                ▼
        PostgreSQL — runs, metrics, claims, traces
                │
                ▼
        React Dashboard
        ├── Score Heatmap
        ├── Failure Explorer
        ├── Trace Viewer
        └── Query Runner
```

---

## Benchmark findings

**Evaluated on:** 28 frozen PubMedQA yes/no questions × 3 strategies = 84 total runs across 5 clinical domains (diabetes, hypertension, asthma, depression, cancer).

**Corpus:** ChatDoctor-HealthCareMagic-100k — 500 records per category, indexed separately per strategy into ChromaDB with cosine similarity.

---

### Finding 1 — No single strategy wins all domains

Domain performance is not uniform across strategies. Strategy B (semantic chunking) leads on diabetes and asthma where topic-coherent chunks improve context quality. Strategy A (fixed chunking) leads on hypertension and depression where the corpus has dense coverage and single-chunk answers are sufficient.

| Domain | Best strategy | Why |
|---|---|---|
| Diabetes | B — Semantic | Mechanism explanations benefit from coherent chunks |
| Asthma | B — Semantic | Treatment protocols span multiple sentences |
| Hypertension | A — Fixed | High corpus density, single-chunk answers sufficient |
| Depression | A — Fixed | Symptom descriptions retrieved well by keyword overlap |
| Cancer | None | All strategies fail — see Finding 2 |

**Deployment implication:** A single pipeline cannot be safely deployed across all clinical domains. Domain-specific routing is required.

---

### Finding 2 — Cancer is the highest-risk domain

Cancer queries hallucinate at 25–40% faithfulness across all three strategies, even when context recall reaches 100% on strategies A and C. The LLM generates unsupported claims even when the retrieved context directly addresses the question.

This is a **pure generation failure** — not a retrieval failure. Switching chunking strategy does not fix it. The failure originates in the LLM's parametric memory overriding the grounding constraint.

```
Cancer domain — Strategy A
  context_recall:  1.00   (right information retrieved)
  faithfulness:    0.28   (LLM ignored it and hallucinated)
  failure_source:  llm    (not retrieval)
```

**Deployment implication:** Cancer queries require human review or answer abstention regardless of pipeline architecture. No RAG configuration tested achieves safe faithfulness thresholds on this domain.

---

### Finding 3 — Context recall plateaus at 0.4–0.5 across all strategies

Context precision is near-perfect across all strategies (0.95–1.0) — the retrieval is finding the right documents. But context recall consistently plateaus at 0.4–0.5 — the retrieved context does not fully cover the reference answer.

This is a **corpus gap**, not a retrieval failure. The ChatDoctor corpus contains patient-doctor conversations, not clinical guidelines. PubMedQA reference answers draw on guideline-level knowledge that the corpus does not contain.

Switching strategies does not close this gap. Extending the corpus with indexed clinical guidelines (NICE, WHO, UpToDate) would directly raise recall.

---

### Finding 4 — Faithfulness vs relevancy is a real deployment tradeoff

Strict grounding constraints (forcing the LLM to answer only from retrieved context) produce high faithfulness but low answer relevancy. The LLM gives safe, grounded answers that do not fully address what was asked.

Relaxing the grounding constraint raises relevancy but introduces hallucination risk. There is no configuration that maximises both simultaneously.

```
Strict prompt:   faithfulness ↑   answer_relevancy ↓
Relaxed prompt:  faithfulness ↓   answer_relevancy ↑
```

**Deployment implication:** This tradeoff must be made explicitly. A system optimised for faithfulness is safer for clinical use. A system optimised for relevancy is more useful but less trustworthy. The right choice depends on whether the deployment context tolerates false negatives or false positives.

---

### Finding 5 — Claim-level evaluation catches failures that answer-level evaluation misses

A strategy that gives a correct yes/no verdict can still contain hallucinated claims. Strategy B correctly answers "Yes, inhaled corticosteroids are recommended for persistent asthma" — but one claim in the answer ("ICS are recommended for controlling inflammation") is marked hallucinated because the retrieved context attributes that phrase to a different drug class.

Answer-level evaluation would score this run as correct. Claim-level evaluation catches the internal inconsistency. For medical applications, this distinction is clinically significant.

---

## Failure source diagnosis

Each run is diagnosed using a two-condition classifier:

```python
if context_recall < 0.5:
    failure_source = "retrieval"   # right info never retrieved
elif faithfulness < 0.5:
    failure_source = "llm"         # right info retrieved, LLM hallucinated
else:
    failure_source = "none"        # pipeline working correctly
```

This surfaces in the Score Heatmap as a failure distribution donut per strategy, and in the Failure Explorer as a filterable column. Teams can use this to decide whether to improve retrieval (better chunking, larger corpus) or constrain generation (tighter prompting, output filtering).

---

## Tech stack

| Component | Technology | Why |
|---|---|---|
| LLM | Groq — llama-3.3-70b-versatile | Fast inference, no local GPU for generation |
| Embeddings | nomic-embed-text via Ollama | Local, no API cost, consistent with indexing |
| Vector DB | ChromaDB | 3 persistent collections, cosine similarity |
| RAGAS evaluation | RAGAS 0.1.x | 4 standard RAG metrics, LangChain-compatible |
| Claim evaluation | Custom DeepEval pipeline | Atomic claim extraction + batch verification |
| Backend | FastAPI + Python | 5 endpoints, async-compatible |
| Database | PostgreSQL | 4 tables: runs, metrics, claims, traces |
| Frontend | React + Vite + Recharts | 4 pages, Axios hooks, live benchmark polling |

---

## Project structure

```
MedRag-Eval/
├── backend/
│   ├── main.py                      5 API endpoints
│   ├── config.py                    Groq + Ollama + ChromaDB config
│   ├── groq_compat.py               LRU-cached client + retry logic
│   ├── benchmark_runner.py          Resumable full testset runner
│   ├── pipelines/
│   │   ├── retrieval.py             MMR reranking + keyword overlap scoring
│   │   ├── strategy_a.py            Fixed chunking pipeline
│   │   ├── strategy_b.py            Semantic chunking pipeline
│   │   └── strategy_c.py            Parent-child chunking pipeline
│   ├── evaluation/
│   │   ├── ragas_runner.py          4 RAGAS metrics + nest_asyncio fix
│   │   ├── deepeval_runner.py       Claim extraction + batch verification
│   │   └── benchmark_metrics.py     Binary verdict extraction
│   ├── ingestion/
│   │   ├── fetcher.py               ChatDoctor + PubMedQA loaders
│   │   └── indexer.py               3 ChromaDB collections
│   ├── db/
│   │   ├── models.py                Run, Metric, Claim, Trace tables
│   │   └── session.py               Connection pool + FastAPI dependency
│   └── testset/
│       ├── qa_pairs.json            28 frozen PubMedQA questions
│       ├── benchmark_results.json   84-run results
│       └── benchmark_progress.json  Resumable progress tracker
├── frontend/
│   └── src/
│       ├── api/client.js            Axios + interceptors
│       ├── hooks/                   useRunQuery, useRuns, useSummary
│       ├── components/ui/           Badge, MetricBar, RiskGauge, ScoreCell
│       ├── components/charts/       FailureDonut (Recharts)
│       ├── components/layout/       NavBar, PageHeader
│       └── pages/
│           ├── QueryRunner.jsx      Live 3-strategy comparison
│           ├── ScoreHeatmap.jsx     RAGAS metrics + deployment recommendation
│           ├── FailureExplorer.jsx  Filterable claim breakdown
│           └── TraceViewer.jsx      Full retrieval provenance
```

---

## Dashboard pages

**Query Runner** — Submit any medical question and see all three strategies answer simultaneously. Live timer, animated score bars, RiskGauge SVG, and claim-level breakdown per strategy side by side.

**Score Heatmap** — Color-coded RAGAS metrics per strategy (green ≥ 80%, amber ≥ 50%, red < 50%). Failure distribution donuts showing retrieval vs LLM failure split. Benchmark findings panel with all 5 key findings. Deployment recommendation panel showing which strategy to use per domain.

**Failure Explorer** — Filterable table of all runs by strategy, domain, and faithfulness threshold. Click any row to expand the full claim breakdown with supporting context per claim.

**Trace Viewer** — Split panel showing the full execution trace: retrieved contexts with similarity scores and MMR ranking, metric tiles, and claim analysis with the specific context chunk that supported or failed each assertion.

---

## How to run

**Prerequisites:** Python 3.11+, Node.js 18+, PostgreSQL, Ollama

```bash
# 1. Pull the embedding model
ollama pull nomic-embed-text

# 2. Set environment variables
cp .env.example .env
# Add GROQ_API_KEY and DATABASE_URL

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Index the corpus (first run only — takes ~30 mins)
python -m backend.ingestion.indexer

# 5. Start the backend
uvicorn backend.main:app --reload

# 6. Start the frontend
cd frontend && npm install && npm run dev

# 7. (Optional) Run the full benchmark
python -m backend.benchmark_runner
```

Open `http://localhost:3000` for the dashboard.
Open `http://localhost:8000/docs` to explore the API directly.

---

## Known limitations

**TruLens incompatibility** — TruLens 0.28.0 is not compatible with Python 3.12. The tracing layer is written and documented but disabled by default. Running on Python 3.11 enables it.

**Strategy C redundant chunks** — Parent-child retrieval occasionally returns near-duplicate parent chunks when multiple children from the same parent are top-ranked. MMR reranking (λ=0.7, similarity threshold=0.92) partially addresses this but does not eliminate it entirely. Adding a stricter deduplication pass before generation would close this gap.

**Corpus coverage ceiling** — Context recall plateaus at 0.4–0.5 because the ChatDoctor corpus is patient-doctor conversation data, not clinical guidelines. Recall cannot exceed what the corpus contains. Extending with NICE guidelines or UpToDate would directly improve this metric.

**Groq rate limits** — The benchmark runner uses a 30-second inter-question delay and 15-second inter-strategy delay to stay within Groq's free tier token limits. These delays extend total benchmark runtime to approximately 90 minutes for 28 questions.

---

## Evaluation methodology

**Eval set:** 28 questions sampled from PubMedQA (pqa_labeled split), filtered to yes/no decisions only, balanced across 5 domains (3 yes + 3 no per domain where available), frozen to disk before benchmarking to prevent contamination across runs.

**Corpus:** ChatDoctor-HealthCareMagic-100k, 500 records per category, held-out eval split separated before indexing to prevent leakage. The same 500 records are indexed into all three ChromaDB collections — the corpus is constant, only the chunking strategy varies.

**Reproducibility:** Generation temperature is fixed at 0 across all runs. The same RAGAS LLM judge (llama-3.3-70b-versatile) is used for all metric computation. Embedding model (nomic-embed-text) is the same at index time and query time. Results are deterministic given the same Groq model weights.

---

## Deployment recommendation

Based on benchmark results, the following deployment guidance applies:

**Deploy Strategy B (Semantic Chunking)** for diabetes and asthma queries. Semantic chunking preserves clinical reasoning chains that fixed boundaries break mid-sentence. Faithfulness and precision are consistently higher in these domains.

**Deploy Strategy A (Fixed Chunking)** for hypertension and depression queries. Lower latency, simpler infrastructure, and the corpus density in these domains means coherent chunks are not required for correct retrieval.

**Do not deploy any strategy** for cancer queries without a human review layer. No configuration tested achieves acceptable faithfulness thresholds. The failure is generative, not retrievable — the LLM's parametric knowledge overrides the grounding constraint. Enforced abstention or mandatory clinician review is the only safe path.