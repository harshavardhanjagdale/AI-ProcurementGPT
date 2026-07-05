"""
Workflow Session Model - Represents a single procurement conversation/workspace.
Each session is an independent workflow with its own chat, state, and lifecycle.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, utc_now


class WorkflowSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="New Procurement", nullable=False)
    rfq_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )  # active, waiting, completed, failed, cancelled
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    langgraph_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="workflow_sessions")
    rfq = relationship("RFQ", backref="workflow_session")
    steps = relationship("WorkflowStep", back_populates="session", lazy="selectin", cascade="all, delete-orphan",
                         order_by="WorkflowStep.started_at")
    events = relationship("WorkflowEvent", back_populates="session", lazy="dynamic", cascade="all, delete-orphan",
                          order_by="WorkflowEvent.created_at")
    messages = relationship("ConversationMessage", back_populates="session", lazy="dynamic", cascade="all, delete-orphan",
                            order_by="ConversationMessage.created_at")
