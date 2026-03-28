# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Groq — used for all LLM generation and eval judging
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    GENERATION_MODEL: str = "llama-3.1-8b-instant"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "3"))
    GROQ_RETRY_BASE_SECONDS: float = float(
        os.getenv("GROQ_RETRY_BASE_SECONDS", "10")
    )
    GROQ_RETRY_MAX_SECONDS: float = float(
        os.getenv("GROQ_RETRY_MAX_SECONDS", "180")
    )

    # Ollama — local embedding server, no API key needed
    # Ollama runs at localhost:11434 by default
    # nomic-embed-text must be pulled: `ollama pull nomic-embed-text`
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:latest")
    EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: int = int(
        os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120")
    )
    RAGAS_JUDGE_PROVIDER: str = os.getenv("RAGAS_JUDGE_PROVIDER", "ollama")
    RAGAS_JUDGE_MODEL: str = os.getenv(
        "RAGAS_JUDGE_MODEL",
        OLLAMA_CHAT_MODEL,
    )

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_store"
    COLLECTION_STRATEGY_A: str = "medrag_strategy_a"
    COLLECTION_STRATEGY_B: str = "medrag_strategy_b"
    COLLECTION_STRATEGY_C: str = "medrag_strategy_c"

    # Retrieval
    TOP_K: int = 5
    RETRIEVAL_CANDIDATE_MULTIPLIER: int = int(
        os.getenv("RETRIEVAL_CANDIDATE_MULTIPLIER", "3")
    )
    STRATEGY_C_ENABLE_DIVERSITY_RERANKING: bool = (
        os.getenv("STRATEGY_C_ENABLE_DIVERSITY_RERANKING", "true").lower()
        in {"1", "true", "yes"}
    )
    RETRIEVAL_MMR_LAMBDA: float = float(
        os.getenv("RETRIEVAL_MMR_LAMBDA", "0.7")
    )
    RETRIEVAL_MAX_SIMILARITY: float = float(
        os.getenv("RETRIEVAL_MAX_SIMILARITY", "0.92")
    )

    # PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Dataset
    DATASET_NAME: str = "lavita/ChatDoctor-HealthCareMagic-100k"
    BENCHMARK_TESTSET_PATH: str = "backend/testset/qa_pairs.json"
    PUBMEDQA_TESTSET_PATH: str = "backend/testset/qa_pairs.json"
    CHATDOCTOR_TESTSET_PATH: str = "backend/testset/qa_pairs_chatdoctor.json"
    MEDICAL_CATEGORIES: list = [
        "diabetes",
        "hypertension", 
        "asthma",
        "depression",
        "cancer"
    ]
    MAX_RECORDS_PER_CATEGORY: int = 500
    CHATDOCTOR_EVAL_RECORDS_PER_CATEGORY: int = int(
        os.getenv("CHATDOCTOR_EVAL_RECORDS_PER_CATEGORY", "20")
    )
    DATA_SPLIT_SEED: int = int(os.getenv("DATA_SPLIT_SEED", "42"))

config = Config()
