# backend/ingestion/fetcher.py

import logging
import hashlib
import random
import re
import sys
from pathlib import Path

import pandas as pd
from datasets import load_dataset

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import config

# Industry practice: every module has its own logger
# Never use print() in production code — you can't control 
# log levels, filter by module, or pipe to monitoring tools
logger = logging.getLogger(__name__)


def _load_hf_dataset(*args, **kwargs):
    """
    Wrap Hugging Face dataset loading with a clearer connectivity error.
    """
    dataset_name = args[0] if args else "dataset"

    try:
        return load_dataset(*args, **kwargs)
    except ConnectionError as exc:
        raise RuntimeError(
            f"Failed to load '{dataset_name}' from Hugging Face. "
            "Check internet access or make sure the dataset is already "
            "cached locally, then retry."
        ) from exc


def clean_text(text: str) -> str:
    """
    Normalize raw doctor response text.
    
    Why this matters: HuggingFace medical datasets have inconsistent
    formatting — extra whitespace, newlines mid-sentence, unicode artifacts.
    Dirty text = noisy embeddings = worse retrieval.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Collapse multiple whitespace/newlines into single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def is_medical_category(text: str, category: str) -> bool:
    """
    Check if a doctor response belongs to a medical category.
    
    Simple keyword matching — not perfect, but sufficient for 
    building a filtered corpus. In production you'd use a classifier.
    
    Why keyword matching here: embedding-based classification would 
    require a second model call per record × 100k records = expensive.
    For dataset construction, keyword filter is the right tradeoff.
    """
    return category.lower() in text.lower()


def fetch_medical_data(limit: int = None) -> list[dict]:
    """
    Load ChatDoctor dataset, filter by medical categories,
    return clean records ready for chunking and indexing.
    
    Returns:
        List of dicts with keys: id, category, question, answer
    
    Why we return dicts not a DataFrame:
    Downstream code (indexer.py) works with individual records.
    Dicts are explicit, serializable, and don't carry DataFrame overhead.
    """
    logger.info(f"Loading dataset: {config.DATASET_NAME}")
    
    # streaming=False loads entire dataset into memory
    # For 100k records this is fine — would use streaming=True 
    # for multi-million record datasets
    dataset = _load_hf_dataset(config.DATASET_NAME, split="train")
    
    # Convert to pandas for fast vectorized filtering
    df = pd.DataFrame(dataset)
    
    logger.info(f"Total records loaded: {len(df)}")
    
    # Validate expected columns exist
    # Fail loud and early — better than silent wrong behavior downstream
    required_columns = {"input", "output"}
    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"Dataset missing expected columns. "
            f"Found: {df.columns.tolist()}, "
            f"Expected: {required_columns}"
        )
    
    records = []
    
    for category in config.MEDICAL_CATEGORIES:
        logger.info(f"Filtering category: {category}")
        
        # Filter rows where doctor's answer mentions the category
        # We filter on 'output' (doctor response) not 'input' (patient question)
        # because we want documents that actually contain medical knowledge
        # about that category — not just questions that mention it
        category_mask = df["output"].apply(
            lambda text: is_medical_category(text, category)
        )
        
        category_df = df[category_mask].head(limit or config.MAX_RECORDS_PER_CATEGORY)
        
        logger.info(
            f"Category '{category}': {len(category_df)} records found"
        )
        
        for idx, row in category_df.iterrows():
            clean_answer = clean_text(row["output"])
            clean_question = clean_text(row["input"])
            
            # Skip records where cleaning left us with empty strings
            if not clean_answer or not clean_question:
                continue
            
            # Skip very short answers — not enough content to chunk meaningfully
            # 100 characters ~ 2 sentences minimum
            if len(clean_answer) < 100:
                continue
                
            records.append({
                "id": f"{category}_{idx}",
                "category": category,
                "question": clean_question,
                "answer": clean_answer
            })
    
    logger.info(f"Total clean records ready for indexing: {len(records)}")
    
    return records


def _deterministic_record_order(record: dict, salt: str) -> str:
    payload = f"{salt}:{record['id']}:{record['question']}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_chatdoctor_train_eval_split(
    limit_per_category: int | None = None,
    eval_records_per_category: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Build a deterministic in-domain train/eval split from ChatDoctor.

    This removes benchmark leakage:
    - train/index records are embedded into Chroma
    - eval records become held-out benchmark questions
    """
    eval_records_per_category = (
        eval_records_per_category
        or config.CHATDOCTOR_EVAL_RECORDS_PER_CATEGORY
    )
    all_records = fetch_medical_data(limit=limit_per_category)

    train_records = []
    eval_testset = []

    for category in config.MEDICAL_CATEGORIES:
        category_records = [
            record for record in all_records
            if record["category"] == category
        ]
        category_records = sorted(
            category_records,
            key=lambda record: _deterministic_record_order(
                record,
                salt=f"{config.DATA_SPLIT_SEED}:{category}",
            ),
        )

        eval_records = category_records[:eval_records_per_category]
        index_records = category_records[eval_records_per_category:]

        logger.info(
            "ChatDoctor split for %s - index=%s eval=%s",
            category,
            len(index_records),
            len(eval_records),
        )

        train_records.extend(index_records)

        for eval_index, record in enumerate(eval_records):
            eval_testset.append({
                "id": f"chatdoctor_{category}_{eval_index}",
                "question": record["question"],
                "reference_answer": record["answer"],
                "final_answer": None,
                "category": category,
                "source": "chatdoctor_heldout",
                "source_record_id": record["id"],
            })

    eval_testset = sorted(
        eval_testset,
        key=lambda record: _deterministic_record_order(
            {
                "id": record["id"],
                "question": record["question"],
            },
            salt=f"{config.DATA_SPLIT_SEED}:eval",
        ),
    )

    logger.info(
        "Built ChatDoctor train/eval split - train=%s eval=%s",
        len(train_records),
        len(eval_testset),
    )
    return train_records, eval_testset

# Category keywords map
# PubMedQA has no explicit category labels
# We infer category from question text — same approach as ChatDoctor
# This ensures eval questions are topically aligned with your corpus
CATEGORY_KEYWORDS = {
    "diabetes": [
        "diabetes", "diabetic", "insulin", "metformin",
        "glycemic", "glucose", "HbA1c"
    ],
    "hypertension": [
        "hypertension", "hypertensive", "blood pressure",
        "antihypertensive", "systolic", "diastolic"
    ],
    "asthma": [
        "asthma", "asthmatic", "bronchial", "inhaler",
        "bronchodilator", "wheeze", "spirometry"
    ],
    "depression": [
        "depression", "depressive", "antidepressant",
        "SSRI", "anxiety", "mental health", "psychiatric"
    ],
    "cancer": [
        "cancer", "tumor", "oncology", "chemotherapy",
        "malignant", "carcinoma", "metastasis"
    ]
}


def detect_category(question: str) -> str | None:
    """
    Detect medical category from question text using keyword matching.

    Returns category string if found, None if question doesn't match
    any of our 5 target categories.

    Why keyword matching not embedding similarity:
    We are doing this across potentially hundreds of questions during
    dataset construction — offline, one time. Keyword matching is
    deterministic, fast, free, and interpretable.
    Embedding-based classification would cost API calls and introduce
    non-determinism for no meaningful accuracy gain here.
    """
    question_lower = question.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in question_lower:
                return category

    return None


def extract_long_answer_text(long_answer: object) -> str:
    """
    Normalize PubMedQA long-answer payloads across dataset versions.

    Some dataset builds expose `long_answer` as a string, others as a
    dict like {"answer": "..."}.
    """
    if isinstance(long_answer, dict):
        answer = long_answer.get("answer", "")
    elif isinstance(long_answer, str):
        answer = long_answer
    else:
        answer = ""

    return clean_text(answer)


def fetch_eval_testset() -> list[dict]:
    """
    Load PubMedQA, filter to yes/no questions aligned with our
    5 medical categories, balance to equal yes/no per category,
    and return structured eval records.

    Returns:
        List of dicts with keys:
        - id: unique identifier for tracing eval results
        - question: medical question string
        - reference_answer: long_answer for RAGAS claim verification
        - final_answer: yes/no for directional accuracy checking
        - category: one of our 5 medical categories

    Why two answer fields:
        reference_answer → RAGAS faithfulness (claim-level verification
                           needs clinical substance not just a verdict)
        final_answer     → directional accuracy check (did system confirm
                           or refute correctly)
    """
    logger.info("Loading PubMedQA dataset")

    dataset = _load_hf_dataset(
        "pubmed_qa",
        "pqa_labeled",
        split="train"
    )

    logger.info(f"Total PubMedQA records: {len(dataset)}")

    # ── Step 1: Filter to yes/no only ──────────────────────────────
    # Exclude "maybe" — undecidable ground truth corrupts faithfulness
    # scoring. RAGAS claim verification against an uncertain reference
    # produces arbitrary scores — noise not signal.
    filtered = [
        item for item in dataset
        if item["final_decision"] in ["yes", "no"]
    ]

    logger.info(f"After yes/no filter: {len(filtered)} records")

    # ── Step 2: Filter short long_answers ──────────────────────────
    # PubMedQA long_answer can be either a plain string or a dict.
    # Normalize it before measuring length. Minimum 150 chars ensures enough
    # clinical substance for RAGAS to extract multiple claims.
    # Too short = only one claim = faithfulness score is binary and
    # unreliable (one wrong claim = 0.0, one right claim = 1.0)
    filtered = [
        item for item in filtered
        if len(extract_long_answer_text(item.get("long_answer"))) >= 150
    ]

    logger.info(f"After minimum length filter: {len(filtered)} records")

    # ── Step 3: Detect and attach category ─────────────────────────
    categorized = []
    for item in filtered:
        category = detect_category(item["question"])
        if category:
            categorized.append({
                **item,
                "detected_category": category
            })

    logger.info(f"After category filter: {len(categorized)} records")

    # ── Step 4: Balance yes/no per category ────────────────────────
    # Target: 6 questions per category × 5 categories = 30 total
    # 3 yes + 3 no per category = balanced within each category
    #
    # Why balance per category not just globally:
    # Global balance of 15 yes / 15 no could mean 10 diabetes yes
    # and 0 diabetes no — your system is never tested on refutation
    # within a specific domain. Per-category balance ensures coverage
    # across all failure modes in all domains.

    TARGET_PER_CATEGORY_PER_LABEL = 3
    records_by_category = {cat: {"yes": [], "no": []} for cat in config.MEDICAL_CATEGORIES}

    for item in categorized:
        cat = item["detected_category"]
        label = item["final_decision"]

        if cat in records_by_category:
            records_by_category[cat][label].append(item)

    rng = random.Random(config.DATA_SPLIT_SEED)

    # Shuffle within each bucket before sampling
    # Deterministic shuffle keeps the frozen eval set stable across reruns.
    for cat in records_by_category:
        rng.shuffle(records_by_category[cat]["yes"])
        rng.shuffle(records_by_category[cat]["no"])

    # ── Step 5: Build final testset ────────────────────────────────
    testset = []

    for cat in config.MEDICAL_CATEGORIES:
        yes_pool = records_by_category[cat]["yes"]
        no_pool = records_by_category[cat]["no"]

        # Warn if not enough questions in a category
        # Don't crash — degrade gracefully and log the gap
        if len(yes_pool) < TARGET_PER_CATEGORY_PER_LABEL:
            logger.warning(
                f"Category '{cat}' has only {len(yes_pool)} yes questions "
                f"(target: {TARGET_PER_CATEGORY_PER_LABEL})"
            )
        if len(no_pool) < TARGET_PER_CATEGORY_PER_LABEL:
            logger.warning(
                f"Category '{cat}' has only {len(no_pool)} no questions "
                f"(target: {TARGET_PER_CATEGORY_PER_LABEL})"
            )

        selected = (
            yes_pool[:TARGET_PER_CATEGORY_PER_LABEL] +
            no_pool[:TARGET_PER_CATEGORY_PER_LABEL]
        )

        for idx, item in enumerate(selected):
            reference_answer = extract_long_answer_text(item.get("long_answer"))
            testset.append({
                # Unique id: category + label + index
                # Needed for tracing eval results back to specific questions
                # in PostgreSQL. Without this you can't answer
                # "which question caused the faithfulness drop in diabetes?"
                "id": f"pubmedqa_{cat}_{item['final_decision']}_{idx}",
                "question": item["question"],

                # long_answer -> clinical substance
                # Used by RAGAS for claim-level faithfulness verification
                "reference_answer": reference_answer,

                # final_decision → yes/no verdict
                # Used for directional accuracy checking
                "final_answer": item["final_decision"],

                "category": cat,
                "source": "pubmedqa"
            })

    # Final shuffle — prevents any category ordering bias
    # in sequential evaluation runs
    rng.shuffle(testset)

    logger.info(f"Final eval testset size: {len(testset)}")
    logger.info(
        f"Distribution: "
        f"{sum(1 for r in testset if r['final_answer'] == 'yes')} yes, "
        f"{sum(1 for r in testset if r['final_answer'] == 'no')} no"
    )

    return testset


def save_pubmedqa_eval_testset(
    output_path: str = config.PUBMEDQA_TESTSET_PATH,
) -> None:
    """
    Fetch eval testset and persist to disk as JSON.

    Why persist to disk:
    You don't want to re-fetch from HuggingFace every eval run.
    Network calls are slow, non-deterministic across runs, and
    HuggingFace could change the dataset. Persisting guarantees
    your eval set is frozen — same questions every run.
    Reproducibility is non-negotiable in evaluation systems.
    """
    import json
    import os

    testset = fetch_eval_testset()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(testset, f, indent=2)

    logger.info(f"PubMedQA eval testset saved to {output_path}")


def save_chatdoctor_eval_testset(
    output_path: str = config.CHATDOCTOR_TESTSET_PATH,
) -> None:
    import json
    import os

    _, testset = build_chatdoctor_train_eval_split(
        limit_per_category=config.MAX_RECORDS_PER_CATEGORY,
        eval_records_per_category=config.CHATDOCTOR_EVAL_RECORDS_PER_CATEGORY,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(testset, f, indent=2)

    logger.info(f"ChatDoctor eval testset saved to {output_path}")


def save_eval_testset(
    output_path: str = config.BENCHMARK_TESTSET_PATH,
    source: str = "pubmedqa",
) -> None:
    if source == "chatdoctor":
        save_chatdoctor_eval_testset(output_path=output_path)
    elif source == "pubmedqa":
        save_pubmedqa_eval_testset(output_path=output_path)
    else:
        raise ValueError(f"Unknown eval testset source: {source}")



     

if __name__ == "__main__":
    # Quick sanity check — run this file directly to verify fetch works
    # python -m backend.ingestion.fetcher
    logging.basicConfig(level=logging.INFO)
    save_eval_testset(source="pubmedqa")
    save_chatdoctor_eval_testset()
    
    records = fetch_medical_data()
    
    print(f"\nTotal records: {len(records)}")
    print(f"\nSample record:")
    print(f"ID: {records[0]['id']}")
    print(f"Category: {records[0]['category']}")
    print(f"Question: {records[0]['question'][:100]}...")
    print(f"Answer: {records[0]['answer'][:200]}...")
