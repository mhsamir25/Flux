from pydantic import BaseModel

from app.nodes.base import FieldSchema, NodeCategory


class NodeCatalogueEntry(BaseModel):
    id: str
    display_name: str
    category: NodeCategory
    config_schema: list[FieldSchema]
    formula_exportable: bool
    # Added for the frontend (Phase 11): the canvas needs to know how many input handles to
    # draw per node type (0 for sources, 2 for join, 1 otherwise) without hardcoding per-node
    # logic — consistent with §5.1's "the frontend never hardcodes per-node UI."
    input_ports: int
    output_ports: int
