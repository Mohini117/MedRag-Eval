# backend/db/models.py

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Text,
    DateTime, ForeignKey, Integer, Enum
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import enum

Base = declarative_base()

# ── Enums ─────────────────────────────────────────────────────────
# Using Python enums + SQLAlchemy Enum type gives you:
# 1. Database-level constraint — invalid values rejected at DB layer
# 2. Python-level type safety — caught before hitting the database
# 3. Self-documenting schema — anyone reading models.py knows
#    exactly what values are valid without reading application code

class PipelineName(str, enum.Enum):
    STRATEGY_A = "strategy_a_fixed_chunking"
    STRATEGY_B = "strategy_b_semantic_chunking"
    STRATEGY_C = "strategy_c_parent_child_chunking"


class FailureSource(str, enum.Enum):
    RETRIEVAL = "retrieval"
    LLM = "llm"
    NONE = "none"


class ClaimStatus(str, enum.Enum):
    SUPPORTED = "supported"
    HALLUCINATED = "hallucinated"
    PARTIAL = "partial"


# ── Runs Table ────────────────────────────────────────────────────
class Run(Base):
    """
    One row per pipeline execution.

    This is the parent table — everything else links back here
    via run_id. If you delete a run, all associated metrics,
    claims, and traces should cascade delete too.

    Why UUID for primary key not auto-increment integer:
    UUIDs are generated in application code before the DB insert.
    This means you can construct foreign key references in memory
    before any database round trip — useful when inserting runs,
    metrics, claims, and traces in a single transaction.
    Auto-increment IDs require a DB round trip to get the ID first.
    """
    __tablename__ = "runs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    question = Column(Text, nullable=False)
    pipeline_name = Column(
        Enum(PipelineName),
        nullable=False
    )
    answer = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    # nullable=True — category may not always be known at run time
    # We infer it from the eval testset question, not the user query

    latency_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships — SQLAlchemy loads related rows automatically
    # when you access run.metrics, run.claims, run.trace
    metrics = relationship(
        "Metric",
        back_populates="run",
        uselist=False,      # 1:1 — one metrics row per run
        cascade="all, delete-orphan"
    )
    claims = relationship(
        "Claim",
        back_populates="run",
        uselist=True,       # 1:many — multiple claims per run
        cascade="all, delete-orphan"
    )
    trace = relationship(
        "Trace",
        back_populates="run",
        uselist=False,      # 1:1 — one trace row per run
        cascade="all, delete-orphan"
    )


# ── Metrics Table ─────────────────────────────────────────────────
class Metric(Base):
    """
    RAGAS scores for a single run.

    Why separate table not columns on Run:
    Separation of concerns. Run table owns execution data.
    Metrics table owns evaluation data. They are written at
    different times — run is written immediately after pipeline
    executes, metrics are written after RAGAS eval completes
    (which takes longer — involves LLM-as-judge calls).

    Keeping them separate means your pipeline can log the run
    immediately without waiting for eval to finish. Eval runner
    updates the metrics table asynchronously.

    All metric columns nullable=True:
    Eval runners populate these after the run is created.
    At run creation time, scores don't exist yet.
    """
    __tablename__ = "metrics"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True         # enforces 1:1 with runs
    )

    # RAGAS metrics
    faithfulness = Column(Float, nullable=True)
    answer_relevancy = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)

    # Derived diagnostic — computed from recall + faithfulness
    # using the logic you derived yourself
    failure_source = Column(
        Enum(FailureSource),
        nullable=True
    )

    evaluated_at = Column(DateTime, nullable=True)

    run = relationship("Run", back_populates="metrics")


# ── Claims Table ──────────────────────────────────────────────────
class Claim(Base):
    """
    Individual claim-level breakdown from DeepEval.

    Why this is the most valuable table in your schema:
    Every other table tells you THAT something failed.
    This table tells you WHAT specifically failed and WHERE.

    One run produces N claims. Each claim is independently
    verified as supported, hallucinated, or partial.

    This powers your Failure Explorer page — you can filter:
    "Show me all hallucinated claims from Strategy A on diabetes"
    That is a query no other RAG eval tool exposes at this level.
    This is what makes your project top 1%.

    claim_index:
    Position of this claim in the answer (0-indexed).
    Lets frontend reconstruct the answer with claims highlighted
    in order — red for hallucinated, green for supported.
    """
    __tablename__ = "claims"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False
    )

    claim_text = Column(Text, nullable=False)
    status = Column(
        Enum(ClaimStatus),
        nullable=False
    )
    claim_index = Column(Integer, nullable=False)

    # Which context chunk (if any) this claim was verified against
    # Null if claim could not be mapped to any retrieved chunk
    supporting_context = Column(Text, nullable=True)

    run = relationship("Run", back_populates="claims")


# ── Traces Table ──────────────────────────────────────────────────
class Trace(Base):
    """
    Full pipeline trace for a single run.

    Why store raw contexts here and not just in the run:
    Contexts are large — storing them on the Run table bloats
    every query against runs even when you don't need contexts.
    Trace table is only joined when the Trace Viewer page
    explicitly requests it. This is called lazy loading —
    expensive data only fetched when needed.

    retrieved_contexts stored as ARRAY(Text):
    PostgreSQL native array type. Preserves order — context[0]
    is the most similar chunk, context[4] is least similar.
    Order matters for debugging retrieval quality.

    raw_pipeline_output:
    Full JSON blob of the pipeline result dict. Stores everything
    — useful as a fallback if you add new fields later and need
    to re-process historical runs without re-running the pipeline.
    """
    __tablename__ = "traces"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True         # enforces 1:1 with runs
    )

    retrieved_contexts = Column(ARRAY(Text), nullable=False)
    context_count = Column(Integer, nullable=False)

    # TruLens populates these after tracing
    groundedness_score = Column(Float, nullable=True)
    context_relevance_min = Column(Float, nullable=True)
    answer_relevance = Column(Float, nullable=True)
    failure_source = Column(
        Enum(FailureSource),
        nullable=True
    )
    trace_id = Column(String(255), nullable=True)
    trulens_feedback = Column(Text, nullable=True)
    raw_pipeline_output = Column(Text, nullable=True)   # JSON string
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("Run", back_populates="trace")


# ── Database Initialization ───────────────────────────────────────
def init_db(engine) -> None:
    """
    Create all tables if they don't exist.

    Why Base.metadata.create_all not Alembic migrations here:
    create_all is sufficient for development and first-time setup.
    Alembic handles schema migrations when you change models
    after data already exists — needed in production.
    For this project, create_all on startup is clean and simple.
    """
    Base.metadata.create_all(bind=engine)
