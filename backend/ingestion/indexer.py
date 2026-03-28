import json
import logging
import sys
import uuid
from pathlib import Path

import chromadb
import requests
from chromadb.config import Settings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import config
from backend.ingestion.fetcher import build_chatdoctor_train_eval_split


logger = logging.getLogger(__name__)
INDEX_PROGRESS_PATH = Path("backend/testset/index_progress.json")

chroma_client = chromadb.PersistentClient(
    path=config.CHROMA_PERSIST_DIR,
    settings=Settings(anonymized_telemetry=False),
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for index, text in enumerate(texts, start=1):
        logger.info(
            "Embedding text %s/%s with model %s",
            index,
            len(texts),
            config.EMBEDDING_MODEL,
        )
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": config.EMBEDDING_MODEL,
                "prompt": text,
            },
            timeout=config.OLLAMA_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        embeddings.append(response.json()["embedding"])
    return embeddings


def chunk_fixed(
    text: str,
    chunk_size: int = 200,
    overlap: int = 40,
) -> list[str]:
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap

    return chunks


def chunk_semantic(text: str) -> list[str]:
    logger.info(
        "Starting semantic chunking for text with %s words",
        len(text.split()),
    )
    splitter = SemanticChunker(
        embeddings=OllamaEmbeddings(
            model=config.EMBEDDING_MODEL,
            base_url=config.OLLAMA_BASE_URL,
        ),
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=85,
    )
    docs = splitter.create_documents([text])
    chunks = [doc.page_content for doc in docs]
    logger.info("Semantic chunking produced %s chunks", len(chunks))
    return chunks


def chunk_parent_child(
    text: str,
    parent_size: int = 400,
    child_size: int = 100,
) -> list[dict]:
    words = text.split()
    chunks = []
    parent_start = 0

    while parent_start < len(words):
        parent_end = parent_start + parent_size
        parent_words = words[parent_start:parent_end]
        parent_text = " ".join(parent_words)

        child_start = 0
        while child_start < len(parent_words):
            child_end = child_start + child_size
            child_text = " ".join(parent_words[child_start:child_end])
            chunks.append({
                "child_text": child_text,
                "parent_text": parent_text,
            })
            child_start += child_size

        parent_start += parent_size

    return chunks


def _make_chunk_id(strategy: str, record_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"medrag:{strategy}:{record_id}:{chunk_index}",
    ))


def _default_progress() -> dict[str, list[str]]:
    return {
        "fixed": [],
        "semantic": [],
        "parent_child": [],
    }


def load_index_progress() -> dict[str, list[str]]:
    if not INDEX_PROGRESS_PATH.exists():
        return _default_progress()

    with open(INDEX_PROGRESS_PATH) as f:
        data = json.load(f)

    progress = _default_progress()
    for key in progress:
        progress[key] = data.get(key, [])
    return progress


def save_index_progress(progress: dict[str, list[str]]) -> None:
    INDEX_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


def clear_index_progress() -> None:
    if INDEX_PROGRESS_PATH.exists():
        INDEX_PROGRESS_PATH.unlink()


def _ensure_progress_matches_collection(
    progress: dict[str, list[str]],
    strategy: str,
    collection,
) -> dict[str, list[str]]:
    if collection.count() == 0 and progress.get(strategy):
        logger.warning(
            "Collection for %s is empty but progress exists. Clearing progress.",
            strategy,
        )
        progress[strategy] = []
        save_index_progress(progress)
    return progress


def _flush_standard_batch(
    *,
    collection,
    batch_texts: list[str],
    batch_metadata: list[dict],
    batch_ids: list[str],
    strategy: str,
) -> tuple[list[str], list[dict], list[str]]:
    if not batch_texts:
        return [], [], []

    embeddings = embed_texts(batch_texts)
    collection.upsert(
        ids=batch_ids,
        embeddings=embeddings,
        documents=batch_texts,
        metadatas=batch_metadata,
    )
    logger.info("Indexed %s chunks for strategy %s", len(batch_texts), strategy)
    return [], [], []


def _flush_parent_child_batch(
    *,
    collection,
    batch_child: list[str],
    batch_parent: list[str],
    batch_metadata: list[dict],
    batch_ids: list[str],
) -> tuple[list[str], list[str], list[dict], list[str]]:
    if not batch_child:
        return [], [], [], []

    embeddings = embed_texts(batch_child)
    collection.upsert(
        ids=batch_ids,
        embeddings=embeddings,
        documents=batch_parent,
        metadatas=batch_metadata,
    )
    logger.info("Indexed %s parent-child chunks", len(batch_child))
    return [], [], [], []


def _index_records(
    records: list[dict],
    collection,
    strategy: str,
    batch_size: int = 50,
) -> None:
    progress = _ensure_progress_matches_collection(
        load_index_progress(),
        strategy,
        collection,
    )
    processed_record_ids = set(progress.get(strategy, []))
    total_records = len(records)
    batch_texts: list[str] = []
    batch_metadata: list[dict] = []
    batch_ids: list[str] = []

    for record_index, record in enumerate(records, start=1):
        if record["id"] in processed_record_ids:
            continue

        logger.info(
            "Chunking record %s/%s for strategy %s (%s)",
            record_index,
            total_records,
            strategy,
            record["id"],
        )

        if strategy == "fixed":
            chunks = chunk_fixed(record["answer"])
        elif strategy == "semantic":
            chunks = chunk_semantic(record["answer"])
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        for chunk_index, chunk in enumerate(chunks):
            batch_texts.append(chunk)
            batch_metadata.append({
                "record_id": record["id"],
                "category": record["category"],
                "source_question": record["question"][:200],
                "strategy": strategy,
            })
            batch_ids.append(_make_chunk_id(strategy, record["id"], chunk_index))

            if len(batch_texts) >= batch_size:
                batch_texts, batch_metadata, batch_ids = _flush_standard_batch(
                    collection=collection,
                    batch_texts=batch_texts,
                    batch_metadata=batch_metadata,
                    batch_ids=batch_ids,
                    strategy=strategy,
                )

        progress[strategy].append(record["id"])
        processed_record_ids.add(record["id"])
        save_index_progress(progress)

    _flush_standard_batch(
        collection=collection,
        batch_texts=batch_texts,
        batch_metadata=batch_metadata,
        batch_ids=batch_ids,
        strategy=strategy,
    )


def _index_records_parent_child(
    records: list[dict],
    collection,
    batch_size: int = 50,
) -> None:
    strategy = "parent_child"
    progress = _ensure_progress_matches_collection(
        load_index_progress(),
        strategy,
        collection,
    )
    processed_record_ids = set(progress.get(strategy, []))
    batch_child: list[str] = []
    batch_parent: list[str] = []
    batch_metadata: list[dict] = []
    batch_ids: list[str] = []

    for record in records:
        if record["id"] in processed_record_ids:
            continue

        logger.info("Chunking parent-child record %s", record["id"])
        chunks = chunk_parent_child(record["answer"])

        for chunk_index, chunk in enumerate(chunks):
            batch_child.append(chunk["child_text"])
            batch_parent.append(chunk["parent_text"])
            batch_metadata.append({
                "record_id": record["id"],
                "category": record["category"],
                "source_question": record["question"][:200],
                "strategy": strategy,
            })
            batch_ids.append(_make_chunk_id(strategy, record["id"], chunk_index))

            if len(batch_child) >= batch_size:
                batch_child, batch_parent, batch_metadata, batch_ids = _flush_parent_child_batch(
                    collection=collection,
                    batch_child=batch_child,
                    batch_parent=batch_parent,
                    batch_metadata=batch_metadata,
                    batch_ids=batch_ids,
                )

        progress[strategy].append(record["id"])
        processed_record_ids.add(record["id"])
        save_index_progress(progress)

    _flush_parent_child_batch(
        collection=collection,
        batch_child=batch_child,
        batch_parent=batch_parent,
        batch_metadata=batch_metadata,
        batch_ids=batch_ids,
    )


def index_strategy_a(records: list[dict]) -> None:
    collection = chroma_client.get_or_create_collection(
        name=config.COLLECTION_STRATEGY_A,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("Indexing Strategy A: Fixed chunking")
    _index_records(records, collection, strategy="fixed")


def index_strategy_b(records: list[dict]) -> None:
    collection = chroma_client.get_or_create_collection(
        name=config.COLLECTION_STRATEGY_B,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("Indexing Strategy B: Semantic chunking")
    _index_records(records, collection, strategy="semantic")


def index_strategy_c(records: list[dict]) -> None:
    collection = chroma_client.get_or_create_collection(
        name=config.COLLECTION_STRATEGY_C,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("Indexing Strategy C: Parent-child chunking")
    _index_records_parent_child(records, collection)


def reset_strategy_collections() -> None:
    for collection_name in [
        config.COLLECTION_STRATEGY_A,
        config.COLLECTION_STRATEGY_B,
        config.COLLECTION_STRATEGY_C,
    ]:
        try:
            chroma_client.delete_collection(collection_name)
            logger.info("Deleted existing collection: %s", collection_name)
        except Exception:
            logger.info("Collection %s did not exist yet; continuing", collection_name)

    clear_index_progress()


def run_full_indexing(reset_existing: bool = False) -> None:
    logger.info("Starting full indexing pipeline")
    logger.info(
        "Fetching up to %s records per category for all strategies",
        config.MAX_RECORDS_PER_CATEGORY,
    )
    records, heldout_eval = build_chatdoctor_train_eval_split(
        limit_per_category=config.MAX_RECORDS_PER_CATEGORY,
        eval_records_per_category=config.CHATDOCTOR_EVAL_RECORDS_PER_CATEGORY,
    )
    logger.info(
        "Using %s held-out ChatDoctor questions for audit-set generation",
        len(heldout_eval),
    )

    testset_path = Path(config.CHATDOCTOR_TESTSET_PATH)
    testset_path.parent.mkdir(parents=True, exist_ok=True)
    with open(testset_path, "w") as f:
        json.dump(heldout_eval, f, indent=2)
    logger.info(
        "Saved held-out ChatDoctor audit set to %s without changing the active benchmark",
        testset_path,
    )

    if reset_existing:
        reset_strategy_collections()

    index_strategy_a(records)
    index_strategy_b(records)
    index_strategy_c(records)
    logger.info("Full indexing complete - all 3 collections ready")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_indexing(reset_existing=False)
