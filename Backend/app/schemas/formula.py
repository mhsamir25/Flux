from pydantic import BaseModel

from app.engine.formula_engine import FormulaResult, ParseError, ParsedPipeline  # noqa: F401
from app.schemas.pipeline import EdgeDefinition, NodeDefinition


class FormulaGenerateRequest(BaseModel):
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]


class FormulaParseRequest(BaseModel):
    formula: str
