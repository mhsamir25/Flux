"""Defines the PipelineTemplate ORM table used to save user pipelines.
- Uses GUID for UUID columns so the same code works on PostgreSQL (native UUID) and SQLite (CHAR(36)).
- owner_id is a foreign key to user.id linking templates to the user who created them.
- pipeline_json uses JSONB on PostgreSQL (supports queries) and falls back to plain JSON on SQLite.
- created_at and updated_at are auto-managed by the database using server_default/onupdate.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db import Base

# JSON type that uses JSONB on Postgres, plain JSON on SQLite
_JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class PipelineTemplate(Base):
    __tablename__ = "pipeline_template"

    # UUID primary key for cross-database compatibility
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    # Foreign key reference to the user who owns this template
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("user.id"), nullable=False)

    # Template display name
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional description of the pipeline
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stored pipeline graph (nodes/connections); JSONB allows querying in production
    pipeline_json: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    # Timestamp set by database on creation
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # Timestamp updated automatically by database on every change
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
