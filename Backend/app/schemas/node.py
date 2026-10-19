"""NodeCatalogueEntry  — what GET /api/nodes serializes registry.all() into.
FieldSchema/NodeCategory are NOT redefined here despite the plan listing "FieldSchema,
NodeCatalogueEntry" together for schemas/node.py — Phase 2 already defined FieldSchema
directly in app/nodes/base.py (tightly coupled with NodePlugin.get_config_schema()'s return
type), so this module imports and reuses it rather than duplicating it under a second name.
"""
from pydantic import BaseModel

from app.nodes.base import FieldSchema, NodeCategory


class NodeCatalogueEntry(BaseModel):
    id: str
    display_name: str
    category: NodeCategory
    config_schema: list[FieldSchema]
    formula_exportable: bool
    input_ports: int
    output_ports: int
