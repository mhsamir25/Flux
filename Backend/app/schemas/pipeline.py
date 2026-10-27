import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class NodeDefinition(BaseModel):
    id: str
    type: str  # matches NodePlugin.id
    config: dict[str, Any] = Field(default_factory=dict)


class EdgeDefinition(BaseModel):
    source_node_id: str
    target_node_id: str
    target_port: Optional[Literal["left", "right"]] = None  # only meaningful for join


class PipelineRequest(BaseModel):
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    csv_data: Optional[str] = None  # raw CSV text, OR:
    data_reference_id: Optional[str] = None  # id from a prior /api/data/upload call
    target_node_id: Optional[str] = None  # partial execution — stop once this node is computed
    preview_offset: int = Field(default=0, ge=0)  # 0-based row offset for paginated 100-row preview
    export_format: Literal["csv", "xlsx"] = "csv"  # output file format for POST /api/pipeline/export
    template_id: Optional[uuid.UUID] = None  # for ExecutionLog attribution only; see above


class ValidateEdgeRequest(BaseModel):
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    proposed_edge: EdgeDefinition


class ValidateEdgeResponse(BaseModel):
    valid: bool
    error_message: Optional[str] = None
