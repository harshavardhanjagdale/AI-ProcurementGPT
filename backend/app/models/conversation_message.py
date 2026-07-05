"""
Conversation Message Model - Chat messages within a workflow session.
Replaces the old chat_history for workflow-based conversations.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class ConversationMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "conversation_messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, event
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(30), default="text", nullable=False
    )  # text, event, decision, attachment, thinking
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    session = relationship("WorkflowSession", back_populates="messages")
