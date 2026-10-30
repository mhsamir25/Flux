"""Defines the ExecutionLog ORM table for tracking pipeline runs.
- Logs every pipeline execution for debugging and auditing.
- template_id links to PipelineTemplate.id but is nullable so guest/ad-hoc runs can be logged.
- status is restricted to 'success' or 'error' by a database CHECK constraint.
- error_summary stores optional text describing what went wrong.
- run_at is set automatically by the database.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ExecutionLog(Base):
    __tablename__ = "execution_log"
    # Database-level constraint ensuring status can only be success or error
    __table_args__ = (
        CheckConstraint("status IN ('success', 'error')", name="ck_execution_log_status"),
    )

    # UUID primary key
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    # Optional link to the saved template; nullable for guest runs
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, ForeignKey("pipeline_template.id"), nullable=True
    )

    # Execution result; enforced by CHECK constraint
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    # Optional message describing errors
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Auto-set timestamp when the log row is created
    run_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
