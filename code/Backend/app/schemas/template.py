import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    pipeline_json: dict[str, Any]


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pipeline_json: Optional[dict[str, Any]] = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    pipeline_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
