from typing import Any, Optional

from pydantic import BaseModel

from app.dataframe.schema import DataSchema


class NodeResult(BaseModel):
    success: bool
    preview_data: Optional[list[dict[str, Any]]] = None  # first 100 rows, JSON-serialized
    total_row_count: Optional[int] = None
    output_schema: Optional[DataSchema] = None
    error_message: Optional[str] = None
    error_suggestion: Optional[str] = None
    error_row_indices: Optional[list[int]] = None  # populated for row-level failures
    skipped: bool = False  # true if an upstream node failed and this was never run


class ExecutionResult(BaseModel):
    node_results: dict[str, NodeResult]  # keyed by node id
