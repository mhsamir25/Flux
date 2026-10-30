from typing import Union

from fastapi import APIRouter, Depends

from app.engine.formula_engine import FormulaEngine, FormulaResult, ParseError, ParsedPipeline
from app.engine.registry import NodeRegistry, get_registry
from app.schemas.formula import FormulaGenerateRequest, FormulaParseRequest

router = APIRouter(prefix="/api/formula", tags=["formula"])


def get_formula_engine(registry: NodeRegistry = Depends(get_registry)) -> FormulaEngine:
    return FormulaEngine(registry)


@router.post("/generate", response_model=FormulaResult)
async def generate_formula(
    payload: FormulaGenerateRequest, engine: FormulaEngine = Depends(get_formula_engine)
) -> FormulaResult:
    return engine.generate(payload.nodes, payload.edges)


@router.post("/parse", response_model=Union[ParsedPipeline, ParseError])
async def parse_formula(
    payload: FormulaParseRequest, engine: FormulaEngine = Depends(get_formula_engine)
) -> Union[ParsedPipeline, ParseError]:
    return engine.parse(payload.formula)
