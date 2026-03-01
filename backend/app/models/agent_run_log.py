import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AgentRunLog(Base):
    __tablename__ = "agent_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)       # next_goal
    evaluation: Mapped[str | None] = mapped_column(Text, nullable=True)    # evaluation_previous_goal
    memory: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    step_end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="logs")
