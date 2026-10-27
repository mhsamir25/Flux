import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user_optional
from app.auth.models import User
from app.csv_io.parser import write_csv
from app.csv_io.xlsx_io import write_xlsx
from app.data_cache import data_reference_cache
from app.db import get_session
from app.engine.executor import DAGExecutor, ExportError, build_graph, kahn_topological_sort
from app.engine.registry import NodeRegistry, get_registry
from app.models.execution_log import ExecutionLog
from app.rate_limit import tiered_rate_limit
from app.schemas.execution import ExecutionResult
from app.schemas.pipeline import PipelineRequest, ValidateEdgeRequest, ValidateEdgeResponse

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def get_executor(registry: NodeRegistry = Depends(get_registry)) -> DAGExecutor:
    # resolve_raw is what lets a read_xlsx node honour its own sheet_name: the cache keeps the
    # original upload bytes so the executor can re-parse the requested sheet instead of
    # returning whichever sheet the upload happened to parse.
    return DAGExecutor(
        registry,
        resolve_reference=data_reference_cache.get,
        resolve_raw=data_reference_cache.get_raw,
    )


@router.post("/execute", response_model=ExecutionResult)
@tiered_rate_limit
async def execute_pipeline(
    payload: PipelineRequest,
    request: Request,  # required by slowapi's @tiered_rate_limit, unused otherwise
    executor: DAGExecutor = Depends(get_executor),
    user: Optional[User] = Depends(current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> ExecutionResult:
    result = executor.execute(payload)
    await _log_execution(session, payload.template_id, result)
    return result


@router.post("/preview", response_model=ExecutionResult)
async def preview_pipeline_page(
    payload: PipelineRequest,
    executor: DAGExecutor = Depends(get_executor),
) -> ExecutionResult:
    """Returns a paginated 100-row slice (via payload.preview_offset and payload.target_node_id)
    without writing an ExecutionLog entry on every page turn."""
    return executor.execute(payload)


async def _log_execution(session: AsyncSession, template_id, result: ExecutionResult) -> None:
    """Best-effort: ExecutionLog is explicitly optional for core functionality (§10) — a
    logging failure (e.g. template_id pointing at a template that no longer exists, or the DB
    being briefly unavailable) must never fail the pipeline execution response itself."""
    status, error_summary = _summarize_execution(result)
    try:
        session.add(ExecutionLog(
            id=uuid.uuid4(), template_id=template_id, status=status, error_summary=error_summary,
        ))
        await session.commit()
    except Exception:
        await session.rollback()


def _summarize_execution(result: ExecutionResult) -> tuple[str, Optional[str]]:
    failures = [r for r in result.node_results.values() if not r.success]
    if not failures:
        return "success", None
    return "error", failures[0].error_message or "Execution failed."


@router.post("/validate-edge", response_model=ValidateEdgeResponse)
async def validate_edge(
    payload: ValidateEdgeRequest, registry: NodeRegistry = Depends(get_registry)
) -> ValidateEdgeResponse:
    node_by_id = {n.id: n for n in payload.nodes}
    proposed = payload.proposed_edge
    source = node_by_id.get(proposed.source_node_id)
    target = node_by_id.get(proposed.target_node_id)

    if source is None or target is None:
        return ValidateEdgeResponse(valid=False, error_message="Both nodes must exist in the pipeline.")
    if source.id == target.id:
        return ValidateEdgeResponse(valid=False, error_message="A node cannot connect to itself.")

    try:
        registry.get(source.type)
    except KeyError:
        return ValidateEdgeResponse(valid=False, error_message=f"Unknown node type '{source.type}'.")
    try:
        target_plugin = registry.get(target.type)
    except KeyError:
        return ValidateEdgeResponse(valid=False, error_message=f"Unknown node type '{target.type}'.")

    existing_to_target = [e for e in payload.edges if e.target_node_id == target.id]
    if target_plugin.input_ports == 0:
        return ValidateEdgeResponse(
            valid=False, error_message=f"{target_plugin.display_name} does not accept an input connection."
        )
    if target_plugin.input_ports >= 2:
        port = proposed.target_port
        if port not in ("left", "right"):
            return ValidateEdgeResponse(valid=False, error_message="Join connections must specify a left or right port.")
        if any(e.target_port == port for e in existing_to_target):
            return ValidateEdgeResponse(valid=False, error_message=f"The {port} input is already connected.")
    elif len(existing_to_target) >= target_plugin.input_ports:
        return ValidateEdgeResponse(
            valid=False, error_message=f"{target_plugin.display_name} already has a connected input."
        )

    all_node_ids = list(node_by_id.keys())
    all_edges = [*payload.edges, proposed]
    in_degree, children, _parents, _parents_by_port = build_graph(all_node_ids, all_edges)
    _sorted_order, cycle_nodes = kahn_topological_sort(all_node_ids, in_degree, children)
    if cycle_nodes:
        return ValidateEdgeResponse(valid=False, error_message="This connection would create a cycle.")

    return ValidateEdgeResponse(valid=True)


@router.post("/export")
async def export_pipeline_data(
    payload: PipelineRequest, executor: DAGExecutor = Depends(get_executor)
) -> Response:
    """Exports a node's COMPLETE output as a real CSV or XLSX file — PLAN.md §14: "fetch full
    row set via a dedicated export call, not just the 100-row preview." `target_node_id` names
    which node's output to export (reusing the field execute() already uses for partial-execution,
    since the meaning — "run the pipeline up to and including this node" — is identical here).
    """
    try:
        flux_df = executor.execute_for_export(payload)
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if payload.export_format == "xlsx":
        xlsx_bytes = write_xlsx(flux_df.df)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{payload.target_node_id}.xlsx"'},
        )

    csv_text = write_csv(flux_df.df)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{payload.target_node_id}.csv"'},
    )
