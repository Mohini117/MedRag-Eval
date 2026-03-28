# MedRAG Eval: Benchmark Review

This document is a technical reading of the current benchmark output in [backend/testset/benchmark_results.json](d:/MedRag-Eval/backend/testset/benchmark_results.json).

I am treating this as a senior engineering review of system behavior, not a marketing summary. The goal is to answer one question plainly:

"What do these results say about the current state of the RAG system?"

## Executive Summary

The system is not yet benchmark-ready for reliable binary medical QA.

The main issue is not one bad strategy. The issue is end-to-end instability:

- benchmark accuracy is very low across all three chunking strategies
- a large fraction of runs return either abstentions or empty answers
- retrieval quality is inconsistent, but answer-generation formatting/failure is also a major bottleneck
- the fastest strategy is not the most reliable
- the strategy with the best retrieval metrics still does not convert that advantage into correct final answers

In short: the current bottleneck is not just chunking. It is the full pipeline contract from retrieval -> generation -> answer normalization.

## Benchmark Scope

The current results cover:

- 28 benchmark questions
- source: `pubmedqa`
- categories:
  - asthma: 6
  - diabetes: 6
  - depression: 6
  - hypertension: 5
  - cancer: 5
- label balance:
  - expected `yes`: 14
  - expected `no`: 14

This is a small benchmark, but it is large enough to show clear failure patterns.

## Top-Level Findings

### 1. Overall question-level success is poor

Out of 28 questions:

- only 3 questions were answered correctly by at least one strategy
- 25 questions were missed by all strategies
- 7 questions were abstained by all strategies

That means the system is currently failing on almost the entire benchmark set.

### 2. Strategy A is the most accurate, but still weak

Per-strategy benchmark accuracy:

- Strategy A (fixed chunking): 10.7%
- Strategy B (semantic chunking): 3.6%
- Strategy C (parent-child): 7.1%

This is the clearest ranking from a benchmark-outcome perspective:

1. Strategy A
2. Strategy C
3. Strategy B

But the important engineering conclusion is that all three are still below an acceptable baseline.

### 3. Strategy C is fastest, but speed is coming with reduced reliability

Average latency:

- Strategy A: 24334.89 ms
- Strategy B: 20850.21 ms
- Strategy C: 9263.64 ms

Strategy C is much faster than the others, but it also returns the highest number of empty answers:

- Strategy A empty answers: 12 / 28
- Strategy B empty answers: 13 / 28
- Strategy C empty answers: 19 / 28

My reading: Strategy C is likely sacrificing robustness for speed. It is not a free win.

### 4. Strategy B retrieves better, but does not close the loop

Average retrieval-oriented metrics:

- Strategy A
  - faithfulness: 0.6901
  - answer relevancy: 0.1328
  - context precision: 0.2941
  - context recall: 0.5471
- Strategy B
  - faithfulness: 0.7185
  - answer relevancy: 0.1932
  - context precision: 0.2481
  - context recall: 0.7552
- Strategy C
  - faithfulness: 0.7241
  - answer relevancy: 0.0644
  - context precision: 0.2574
  - context recall: 0.4432

Strategy B has the strongest `context_recall` by a clear margin, and also the best `answer_relevancy`.

That matters because it tells us semantic chunking is helping retrieval.

But benchmark accuracy is still worst for Strategy B.

My conclusion: retrieval improvement alone is not enough. The generation stage is not reliably converting retrieved evidence into benchmark-compatible, correct binary answers.

### 5. Abstention behavior is high and uneven

Abstain rate:

- Strategy A: 46.4%
- Strategy B: 46.4%
- Strategy C: 25.0%

This suggests:

- Strategy A and B are more conservative
- Strategy C is less likely to abstain, but that does not translate into better correctness

In other words, Strategy C is not confidently right. It is simply less likely to say "I cannot answer".

### 6. Category coverage is very uneven

Questions with at least one correct strategy:

- depression: 2 / 6
- asthma: 1 / 6
- diabetes: 0 / 6
- hypertension: 0 / 5
- cancer: 0 / 5

This is a major signal.

The current pipeline has almost no practical success on diabetes, hypertension, and cancer in this benchmark slice.

That usually points to one or more of the following:

- domain mismatch between indexed corpus and benchmark questions
- retrieval surfacing loosely related consumer-health text instead of evidence aligned to PubMedQA-style questions
- answer-generation prompts not constrained strongly enough for binary biomedical QA

## What Worries Me Most

### 1. Empty answers are a bigger problem than chunking

Many failed benchmark verdicts are not just "wrong answers". They are empty outputs.

Predicted verdict could not be extracted for:

- Strategy A: 12 runs
- Strategy B: 13 runs
- Strategy C: 19 runs

In the current evaluator, a verdict is only recognized when the answer:

- starts with `yes`, `no`, or `maybe`, or
- uses the exact abstention phrase

For many failures, the answer is actually blank, not just verbose.

As an engineer, I would treat this as a pipeline reliability defect before I treat it as a retrieval-quality defect.

### 2. Failure-source observability is incomplete

A large share of runs still show `unknown` failure source in aggregate analysis because diagnostic fields are missing or unevaluated.

That makes it harder to answer the most useful debugging question:

"Did we fail because we retrieved the wrong evidence, or because the model ignored good evidence?"

You need that distinction to improve the right layer.

### 3. RAGAS metrics and benchmark outcomes are not aligned enough yet

Some questions show strong faithfulness scores but still fail the binary benchmark.

That means your system can produce an answer that is "faithful to retrieved context" while still being useless for the benchmark task.

This is not a contradiction. It means the retrieved context itself may be irrelevant to the benchmark question, or the answer is not normalized into the required format.

## Strategy-by-Strategy Assessment

### Strategy A: Fixed Chunking

What I see:

- best benchmark accuracy
- slowest overall
- middling retrieval metrics
- high abstention rate

Interpretation:

Fixed chunking is currently the safest default among the three, but it is not strong enough to be called good. It looks comparatively stable, not comparatively excellent.

### Strategy B: Semantic Chunking

What I see:

- best context recall
- best answer relevancy
- worst benchmark accuracy
- high abstention rate

Interpretation:

This strategy is the most interesting technically. It appears to retrieve more relevant material, but the rest of the pipeline is not capitalizing on it. If I were continuing this project, this is the strategy I would keep experimenting on because the retrieval signal is strongest.

### Strategy C: Parent-Child Chunking

What I see:

- fastest by a large margin
- highest faithfulness average
- lowest recall
- most empty answers

Interpretation:

This strategy currently looks operationally attractive but behaviorally fragile. I would not promote it on speed alone because the empty-answer rate is too high.

## Hardest and Easiest Cases

Most successful question:

- `Fast foods - are they a risk factor for asthma?`
- all 3 strategies answered this correctly

Other relatively better cases:

- `Does depression diagnosis and antidepressant prescribing vary by location?`
- 2 strategies answered correctly

Hard failure cases included:

- `Does the use of atypical antipsychotics as adjunctive therapy in depression result in cost savings?`
- `Do nomograms designed to predict biochemical recurrence (BCR) do a better job of predicting more clinically relevant prostate cancer outcomes than BCR?`
- `Does a family meetings intervention prevent depression and anxiety in family caregivers of dementia patients?`
- `Is there a connection between sublingual varices and hypertension?`

These are useful regression-test candidates because they expose the current failure modes clearly.

## My Engineering Interpretation

If I were reviewing this system as a senior engineer, I would say:

1. The benchmark does not currently support any claim that the system is reliable for binary medical QA.
2. Chunking strategy matters, but it is not the primary blocker.
3. The biggest problems are:
   - empty/unstable answer generation
   - weak task-format control for `yes/no/maybe`
   - corpus mismatch between consumer-health retrieval data and PubMedQA-style evaluation questions
4. Strategy B is the best research direction.
   - It has the strongest retrieval signal.
   - It likely needs a stricter answer-generation layer and stronger output formatting.
5. Strategy C should not be chosen just because it is fast.
   - The empty-answer rate is too high.

## Recommended Next Steps

### Immediate

- enforce a strict answer schema
  - first token must be `yes`, `no`, `maybe`, or the abstain phrase
- treat empty answers as first-class failures in logs and UI
- save raw prompt, raw model output, and post-processed output separately
- make failure-source classification mandatory when metrics exist

### Retrieval

- inspect retrieved contexts for failed diabetes, hypertension, and cancer questions
- measure corpus overlap between ChatDoctor-style source material and PubMedQA benchmark questions
- consider benchmarking on an evaluation set closer to the indexed corpus, or indexing a corpus closer to PubMedQA

### Generation

- tighten prompting for binary biomedical QA
- require:
  - line 1: verdict (`yes` or `no` or `maybe`)
  - line 2+: rationale
- add retry or fallback when the model returns an empty answer

### Evaluation

- separate these failure buckets in reporting:
  - retrieval miss
  - answer-format failure
  - empty generation
  - wrong clinical conclusion
- keep benchmark accuracy as the primary KPI
- use RAGAS as supporting diagnostics, not as proof of product quality

## Bottom Line

The current benchmark results are valuable because they are honest.

They do not show that one strategy has already won. They show that the system still needs work on task alignment, output reliability, and corpus fit.

If I had to summarize the state of the project in one sentence:

The retrieval experiments are promising, but the product-level QA pipeline is still failing too often to be considered dependable.
