"""Database schema.

Three tables carry the whole system:

  content_queue    the contract row between Project 1 (Brain) and Project 2 (Hands)
  feedback_memory  the closed-loop "lessons learned" store — the key differentiator
  leads            prospects discovered, scored and drafted for outreach

Statuses are stored as plain strings rather than native database enums so the
schema is portable between SQLite and PostgreSQL without a migration.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Controlled vocabularies
# --------------------------------------------------------------------------- #


class ContentStatus(str, Enum):
    """Lifecycle of a row in content_queue.

    pending -> approved -> scheduled -> published   (the happy path)
    """

    PENDING = "pending"                          # awaiting human review
    APPROVED = "approved"                        # human approved; Project 2 may publish
    REJECTED = "rejected"                        # human rejected; feedback captured
    SCHEDULED = "scheduled"                      # handed to the posting API
    PUBLISHED = "published"                      # live
    MANUAL_INTERVENTION = "manual_intervention"  # circuit breaker tripped
    FAILED = "failed"                            # unrecoverable pipeline error


class Brand(str, Enum):
    JADE = "Jade"                        # jewellers block
    JAGUAR_TRANSIT = "Jaguar Transit"    # high-value goods transit
    DOCTORSHIELD = "DoctorShield"        # medical indemnity


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    X = "x"
    TIKTOK = "tiktok"
    BLOG = "blog"


class Language(str, Enum):
    EN = "en"   # English      — Singapore / Hong Kong
    MS = "ms"   # Malay        — Malaysia
    ID = "id"   # Bahasa Indonesia — Indonesia
    TH = "th"   # Thai         — Thailand
    ZH = "zh"   # Chinese      — Singapore / Hong Kong


class ErrorTag(str, Enum):
    """Controlled rejection tags. The dashboard offers exactly these."""

    TOO_SALESY = "too_salesy"
    INACCURATE_CLAIM = "inaccurate_claim"
    OFF_BRAND_TONE = "off_brand_tone"
    WRONG_CTA = "wrong_cta"
    COMPLIANCE_RISK = "compliance_risk"
    POOR_LOCALISATION = "poor_localisation"
    FACTUAL_ERROR = "factual_error"
    OTHER = "other"


class LeadStatus(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    DRAFTED = "drafted"
    APPROVED = "approved"
    CONTACTED = "contacted"
    DISQUALIFIED = "disqualified"


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


class ContentQueue(Base):
    """Every asset the system produces is one row here.

    This table is the contract between Project 1 and Project 2: Project 1 writes
    rows, Project 2 reads rows where status == 'approved'.  Nothing publishes
    without a human moving a row into that state.
    """

    __tablename__ = "content_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- targeting ---
    brand: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    language: Mapped[str] = mapped_column(String(8), index=True, default=Language.EN.value)
    content_type: Mapped[str] = mapped_column(String(32), default="post")
    topic: Mapped[str | None] = mapped_column(String(512), default=None)
    variant_label: Mapped[str | None] = mapped_column(String(16), default=None)  # A/B

    # --- payload ---
    draft_content: Mapped[str] = mapped_column(Text)
    final_content: Mapped[str | None] = mapped_column(Text, default=None)  # after human edit
    media_path: Mapped[str | None] = mapped_column(String(512), default=None)
    image_paths: Mapped[list[str] | None] = mapped_column(JSON, default=None)  # one hero shot, or one per carousel slide
    healed_content: Mapped[str | None] = mapped_column(Text, default=None)
    audit_transcript: Mapped[str | None] = mapped_column(Text, default=None)
    formats_json: Mapped[str | None] = mapped_column(Text, default=None)  # multi-format pack

    # --- state machine ---
    status: Mapped[str] = mapped_column(String(32), index=True, default=ContentStatus.PENDING.value)
    compliance_errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    # Demo segregation: True only for explicitly-labeled demonstration writes.
    # Real metrics and real publish paths exclude these rows.
    is_demo: Mapped[bool] = mapped_column(default=False, index=True)

    # --- human review ---
    feedback_reason: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # --- publishing (Project 2 writes these back) ---
    external_post_id: Mapped[str | None] = mapped_column(String(128), default=None)
    published_url: Mapped[str | None] = mapped_column(String(512), default=None)
    scheduled_for: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # --- audit ---
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_queue_status_created", "status", "created_at"),
        Index("ix_queue_brand_platform", "brand", "platform"),
    )

    def __repr__(self) -> str:
        return f"<ContentQueue id={self.id} {self.brand}/{self.platform}/{self.language} {self.status}>"


class FeedbackMemory(Base):
    """The closed-loop memory store.

    Written every time a human rejects or edits an asset.  Read before every
    generation and injected into the content agent's system prompt so the same
    mistake is not repeated.  This is what makes the system measurably improve.
    """

    __tablename__ = "feedback_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    error_tag: Mapped[str] = mapped_column(String(64), index=True)
    human_note: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Additive (not in the original six-column spec): traceability back to the
    # rejected asset, so rejection rate and edit distance can be computed.
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_queue.id", ondelete="SET NULL"), default=None
    )

    # Demo segregation: True only for explicitly-labeled walkthrough rows.
    is_demo: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        # Serves the retrieval query: WHERE brand=? AND platform=? ORDER BY timestamp DESC
        Index("ix_feedback_brand_platform_ts", "brand", "platform", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<FeedbackMemory id={self.id} {self.brand}/{self.platform} {self.error_tag}>"


class Lead(Base):
    """A prospect discovered from public sources, scored for fit."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    company_name: Mapped[str] = mapped_column(String(256), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), default=None)
    contact_role: Mapped[str | None] = mapped_column(String(128), default=None)
    email: Mapped[str | None] = mapped_column(String(256), default=None)
    phone: Mapped[str | None] = mapped_column(String(64), default=None)
    website: Mapped[str | None] = mapped_column(String(512), default=None)

    country: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    segment: Mapped[str | None] = mapped_column(String(64), index=True, default=None)  # jeweller | clinic | sme | courier
    target_brand: Mapped[str | None] = mapped_column(String(64), index=True, default=None)

    source_url: Mapped[str | None] = mapped_column(String(512), default=None)
    fit_score: Mapped[int | None] = mapped_column(Integer, index=True, default=None)  # 0-100
    score_rationale: Mapped[str | None] = mapped_column(Text, default=None)
    outreach_draft: Mapped[str | None] = mapped_column(Text, default=None)

    status: Mapped[str] = mapped_column(String(32), index=True, default=LeadStatus.NEW.value)

    # Demo segregation: True only for explicitly-labeled walkthrough rows.
    is_demo: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_leads_segment_score", "segment", "fit_score"),)

    def __repr__(self) -> str:
        return f"<Lead id={self.id} {self.company_name} score={self.fit_score}>"


class PublishEvent(Base):
    """Audit + analytics log for Project 2. One row per publish attempt / webhook / engagement snapshot.

    Keeps engagement out of feedback_reason hack — queryable for the analytics loop.
    """

    __tablename__ = "publish_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_queue.id", ondelete="SET NULL"), default=None, index=True
    )
    event: Mapped[str] = mapped_column(String(32), index=True)  # scheduled | published | failed | webhook | engagement
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    external_post_id: Mapped[str | None] = mapped_column(String(128), default=None)
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<PublishEvent id={self.id} content={self.content_id} {self.event}>"
