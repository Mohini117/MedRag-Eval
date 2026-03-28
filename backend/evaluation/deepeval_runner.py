# backend/evaluation/deepeval_runner.py

import logging
import json
import time
from backend.config import config
from backend.groq_compat import create_chat_completion

logger = logging.getLogger(__name__)

# Valid statuses — must match ClaimStatus enum in db/models.py
# Centralizing here means one place to update if enum changes
VALID_STATUSES = {"supported", "hallucinated", "partial"}


def extract_claims(answer: str) -> list[str]:
    """
    Break generated answer into atomic factual claims.

    Why atomic claims:
    An atomic claim makes exactly one verifiable assertion.
    "Metformin reduces blood sugar and is safe for kidneys"
    is two claims — one might be supported, one might not.
    Splitting atomically gives you precise per-claim verdicts.

    Why JSON output format:
    Parsing JSON is deterministic. Parsing free text is fragile —
    newline splitting breaks if LLM adds numbering, bullets,
    or extra explanation. JSON gives you a clean list every time.
    """
    prompt = f"""Break the following medical answer into atomic factual claims.
Each claim must make exactly one verifiable assertion.
Return ONLY a JSON array of strings. No explanation, no numbering.

Example output format:
["claim one here", "claim two here", "claim three here"]

Answer to break down:
{answer}"""

    try:
        response = create_chat_completion(
            model=config.GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if LLM adds them
        # Llama3 sometimes wraps JSON in ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        claims = json.loads(raw)

        # Validate we got a list of strings
        if not isinstance(claims, list):
            raise ValueError(f"Expected list, got {type(claims)}")

        claims = [str(c).strip() for c in claims if str(c).strip()]

        logger.info(f"Extracted {len(claims)} atomic claims from answer")
        return claims

    except Exception as e:
        logger.error(f"Claim extraction failed: {str(e)}")
        # Fallback: split on periods as rough sentence boundary
        # Better than returning empty list — at least something
        # gets evaluated even if atomicity is imperfect
        fallback = [s.strip() for s in answer.split(".") if len(s.strip()) > 20]
        logger.warning(f"Using fallback claim extraction: {len(fallback)} claims")
        return fallback


def verify_claims_batch(
    claims: list[str],
    contexts: list[str]
) -> list[dict]:
    """
    Verify all claims against retrieved contexts in a single LLM call.

    Why batch not sequential:
    Sequential = N API calls for N claims.
    Batch = 1 API call for all claims.
    For 6 claims: 6x faster, 6x cheaper, same accuracy.

    Why we include context index in output:
    Knowing which specific context chunk supported a claim
    lets the frontend highlight both the claim and its source.
    This is the provenance chain: answer claim → context chunk.

    Prompt engineering note:
    We give the LLM numbered contexts so it can reference
    them by index in its response. "supported_by_context: 2"
    is unambiguous. "supported by the second paragraph" is not.
    """
    context_str = "\n\n".join(
        f"[Context {i}]: {ctx}"
        for i, ctx in enumerate(contexts)
    )

    claims_str = "\n".join(
        f"{i}. {claim}"
        for i, claim in enumerate(claims)
    )

    prompt = f"""You are a medical fact-checker. 
Evaluate each claim against the provided context chunks.

For each claim return:
- status: exactly one of: supported / hallucinated / partial
  supported   = claim is fully supported by context
  hallucinated = claim contradicts context or has no basis in context  
  partial     = claim is partially supported but adds unsupported details

- supporting_context_index: index of context that best supports the claim
  Use -1 if no context supports it.

Return ONLY a JSON array. One object per claim. No explanation.

Output format:
[
  {{"claim_index": 0, "status": "supported", "supporting_context_index": 2}},
  {{"claim_index": 1, "status": "hallucinated", "supporting_context_index": -1}}
]

Context chunks:
{context_str}

Claims to evaluate:
{claims_str}"""

    try:
        response = create_chat_completion(
            model=config.GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        verdicts = json.loads(raw)

        # Validate and sanitize each verdict
        sanitized = []
        for v in verdicts:
            status = str(v.get("status", "")).lower().strip()

            # If LLM returns invalid status — default to partial
            # Partial is the safest default — neither confirms nor
            # dismisses the claim. Better than silently dropping it.
            if status not in VALID_STATUSES:
                logger.warning(
                    f"Invalid status '{status}' for claim "
                    f"{v.get('claim_index')} — defaulting to partial"
                )
                status = "partial"

            supporting_idx = int(v.get("supporting_context_index", -1))

            # Resolve supporting context text from index
            # -1 means no supporting context found
            supporting_context = None
            if 0 <= supporting_idx < len(contexts):
                supporting_context = contexts[supporting_idx]

            sanitized.append({
                "claim_index": int(v.get("claim_index", 0)),
                "status": status,
                "supporting_context": supporting_context
            })

        return sanitized

    except Exception as e:
        logger.error(f"Batch claim verification failed: {str(e)}")
        # Return all claims as partial on failure
        # Partial = uncertain = honest about the failure
        return [
            {
                "claim_index": i,
                "status": "partial",
                "supporting_context": None
            }
            for i in range(len(claims))
        ]


def evaluate_with_deepeval(
    answer: str,
    contexts: list[str],
    run_id: str = None
) -> list[dict]:
    """
    Full claim-level hallucination evaluation.

    Pipeline:
    1. Extract atomic claims from answer
    2. Verify all claims against contexts in one batch call
    3. Merge claim text with verification results
    4. Return structured list matching Claim DB model

    Returns:
        List of dicts with keys:
        - claim_text: the actual claim string
        - claim_index: position in answer (0-indexed)
        - status: supported / hallucinated / partial
        - supporting_context: context chunk that verified it (or None)

    This maps directly to your Claim SQLAlchemy model —
    each dict in this list becomes one row in the claims table.
    """
    logger.info(
        f"Starting DeepEval claim analysis — "
        f"run_id: {run_id}"
    )

    start_time = time.time()

    # Step 1: Extract atomic claims
    claims = extract_claims(answer)

    if not claims:
        logger.warning(f"No claims extracted — run_id: {run_id}")
        return []

    # Step 2: Verify all claims in one batch call
    verdicts = verify_claims_batch(claims, contexts)

    # Step 3: Merge claim text with verification results
    # verdicts are indexed by claim_index
    verdict_lookup = {v["claim_index"]: v for v in verdicts}

    results = []
    for i, claim_text in enumerate(claims):
        verdict = verdict_lookup.get(i, {
            "status": "partial",
            "supporting_context": None
        })

        results.append({
            "claim_text": claim_text,
            "claim_index": i,
            "status": verdict["status"],
            "supporting_context": verdict["supporting_context"]
        })

    eval_time = time.time() - start_time

    # Summary logging — useful for spotting patterns
    status_counts = {s: 0 for s in VALID_STATUSES}
    for r in results:
        status_counts[r["status"]] += 1

    logger.info(
        f"DeepEval complete — "
        f"run_id: {run_id}, "
        f"claims: {len(results)}, "
        f"supported: {status_counts['supported']}, "
        f"hallucinated: {status_counts['hallucinated']}, "
        f"partial: {status_counts['partial']}, "
        f"time: {eval_time:.1f}s"
    )

    return results
'''
MEDRAG EVAL — PROGRESS CARD v6
---

## What I added beyond your draft

| Addition | Reason |
|---|---|
| JSON output format for extraction | Deterministic parsing — no fragile newline splitting |
| Markdown fence stripping | GPT wraps JSON in fences inconsistently |
| Fallback claim extraction | Graceful degradation if JSON parse fails |
| Batch verification | 1 API call instead of N — faster and cheaper |
| Status validation + sanitization | Invalid LLM output never reaches PostgreSQL |
| supporting_context tracked | Claim provenance for Failure Explorer |
| claim_index tracked | Frontend can highlight claims in order |
| Status summary logging | Spot hallucination patterns across runs |

---

## Progress card — save this
```
MEDRAG EVAL — PROGRESS CARD v6

Completed:
✓ config.py
✓ fetcher.py (ChatDoctor + PubMedQA)
✓ indexer.py (3 chunking strategies)
✓ strategy_a/b/c.py (3 pipelines)
✓ db/models.py + db/session.py
✓ ragas_runner.py (4 metrics + batch eval)
✓ deepeval_runner.py (claim-level hallucination)

Next:
→ trulens_runner.py (pipeline tracing)
→ main.py (FastAPI — 4 endpoints)
→ React frontend (4 pages)

Key decisions:
- Batch claim verification = 1 API call not N
- JSON output format = deterministic parsing
- Invalid status defaults to partial not crash
- supporting_context tracked per claim
'''
