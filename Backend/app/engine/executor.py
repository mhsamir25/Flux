from collections import deque
from typing import Any, Callable, Optional

from app.dataframe.frame import FluxDataFrame
from app.engine.error_messages import suggest_fix, to_plain_english
from app.engine.registry import NodeRegistry
from app.nodes.base import NodeCategory, NodePlugin, SchemaValidationError
from app.schemas.execution import ExecutionResult, NodeResult
from app.schemas.pipeline import NodeDefinition, PipelineRequest

ResolveReference = Callable[[str], Optional[FluxDataFrame]]
ResolveRaw = Callable[[str], Optional[bytes]]


class ExportError(Exception):


class DAGExecutor:
    def __init__(self, registry: NodeRegistry, resolve_reference: Optional[ResolveReference] = None,
                 resolve_raw: Optional[ResolveRaw] = None):
        self.registry = registry
        self.resolve_reference = resolve_reference
        self.resolve_raw = resolve_raw

    def execute(self, request: PipelineRequest) -> ExecutionResult:
        node_results, _node_outputs = self._run(request)
        return ExecutionResult(node_results=node_results)

    def execute_for_export(self, request: PipelineRequest) -> FluxDataFrame:

        if not request.target_node_id:
            raise ExportError("target_node_id is required to know which node's output to export.")
        node_results, node_outputs = self._run(request)
        result = node_results.get(request.target_node_id)
        if result is None:
            raise ExportError(f"Node '{request.target_node_id}' not found in this pipeline.")
        if not result.success:
            raise ExportError(result.error_message or "This node did not execute successfully.")
        return node_outputs[request.target_node_id]

    def _run(self, request: PipelineRequest) -> tuple[dict[str, NodeResult], dict[str, FluxDataFrame]]:
        node_by_id: dict[str, NodeDefinition] = {n.id: n for n in request.nodes}
        node_ids = list(node_by_id.keys())

        in_degree, children, parents, parents_by_port = build_graph(node_ids, request.edges)

        node_results: dict[str, NodeResult] = {}
        failed_nodes: set[str] = set()

        sorted_order, cycle_nodes = kahn_topological_sort(node_ids, in_degree, children)
        if cycle_nodes:
            cycle_message = f"Your pipeline has a cycle involving: {', '.join(cycle_nodes)}"
            for node_id in cycle_nodes:
                node_results[node_id] = NodeResult(success=False, error_message=cycle_message)
                failed_nodes.add(node_id)

        plugin_by_id: dict[str, NodePlugin] = {}
        for node_id in sorted_order:
            node_def = node_by_id[node_id]
            try:
                plugin_by_id[node_id] = self.registry.get(node_def.type)
            except KeyError:
                node_results[node_id] = NodeResult(
                    success=False, error_message=f"Unknown node type '{node_def.type}'."
                )
                failed_nodes.add(node_id)

        for node_id in sorted_order:
            if node_id in failed_nodes:
                continue
            plugin = plugin_by_id[node_id]
            error = _check_required_inputs(plugin, node_id, parents, parents_by_port)
            if error is not None:
                node_results[node_id] = NodeResult(success=False, error_message=error)
                failed_nodes.add(node_id)

        if request.target_node_id and request.target_node_id in sorted_order:
            cutoff = sorted_order.index(request.target_node_id)
            sorted_order = sorted_order[: cutoff + 1]

        node_outputs: dict[str, FluxDataFrame] = {}
        for node_id in sorted_order:
            if node_id in failed_nodes:
                continue

            if any(parent in failed_nodes for parent in parents.get(node_id, [])):
                node_results[node_id] = NodeResult(
                    success=False, skipped=True,
                    error_message="Upstream node failed; this node was not run",
                )
                failed_nodes.add(node_id)
                continue

            node_def = node_by_id[node_id]
            plugin = plugin_by_id[node_id]
            config = node_def.config or {}

            try:
                error_row_indices = None
                if plugin.category == NodeCategory.SOURCE:
                    output = self._execute_source(plugin, node_def, request)
                elif plugin.id == "join":
                    by_port = parents_by_port.get(node_id, {})
                    left = node_outputs[by_port["left"]]
                    right = node_outputs[by_port["right"]]
                    output = plugin.execute_join(left, right, config)
                else:
                    parent_output = node_outputs[parents[node_id][0]]
                    plugin.infer_output_schema(parent_output.schema, config)
                    output = plugin.execute(parent_output, config)
                    error_row_indices = plugin.compute_row_errors(parent_output, output, config)

                node_outputs[node_id] = output
                node_results[node_id] = NodeResult(
                    success=True,
                    preview_data=output.preview(100).to_json_records(),
                    total_row_count=output.total_row_count,
                    output_schema=output.schema,
                    error_row_indices=error_row_indices,
                )
            except SchemaValidationError as e:
                node_results[node_id] = NodeResult(success=False, error_message=str(e))
                failed_nodes.add(node_id)
            except Exception as e:
                node_results[node_id] = NodeResult(
                    success=False,
                    error_message=to_plain_english(e),
                    error_suggestion=suggest_fix(e),
                )
                failed_nodes.add(node_id)

        return node_results, node_outputs

    def _execute_source(
        self, plugin: NodePlugin, node_def: NodeDefinition, request: PipelineRequest
    ) -> FluxDataFrame:
        config = node_def.config or {}
        resolved = _resolve_source_data(node_def, request, self.resolve_reference)
        reference_id = config.get("data_reference_id") or request.data_reference_id
        if (
            resolved is not None and resolved[0] == "parsed"
            and reference_id and plugin.requires_reparse(config) and self.resolve_raw is not None
        ):
            raw = self.resolve_raw(reference_id)
            if raw is not None:
                reparse_config = dict(config)
                reparse_config["_xlsx_bytes"] = raw
                return plugin.execute_source(reparse_config)

        if resolved is not None and resolved[0] == "parsed":
            return resolved[1]

        injected_config = dict(config)
        if resolved is not None and plugin.id == "read_csv":
            injected_config["_csv_text"] = resolved[1]
        return plugin.execute_source(injected_config)


def build_graph(node_ids: list[str], edges) -> tuple[dict, dict, dict, dict]:
    node_id_set = set(node_ids)
    in_degree = {n: 0 for n in node_ids}
    children: dict[str, list[str]] = {n: [] for n in node_ids}
    parents: dict[str, list[str]] = {n: [] for n in node_ids}
    parents_by_port: dict[str, dict[str, str]] = {}

    for edge in edges:
        if edge.source_node_id not in node_id_set or edge.target_node_id not in node_id_set:
            continue  # references a node id not in this request — dropped, see module docstring
        children[edge.source_node_id].append(edge.target_node_id)
        parents[edge.target_node_id].append(edge.source_node_id)
        in_degree[edge.target_node_id] += 1
        if edge.target_port:
            parents_by_port.setdefault(edge.target_node_id, {})[edge.target_port] = edge.source_node_id

    return in_degree, children, parents, parents_by_port


def kahn_topological_sort(
    node_ids: list[str], in_degree: dict[str, int], children: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    working_in_degree = dict(in_degree)
    queue = deque(n for n in node_ids if working_in_degree[n] == 0)
    sorted_order: list[str] = []

    while queue:
        node_id = queue.popleft()
        sorted_order.append(node_id)
        for child in children[node_id]:
            working_in_degree[child] -= 1
            if working_in_degree[child] == 0:
                queue.append(child)

    cycle_nodes = [n for n in node_ids if n not in sorted_order]
    return sorted_order, cycle_nodes


def _check_required_inputs(
    plugin: NodePlugin, node_id: str, parents: dict[str, list[str]], parents_by_port: dict[str, dict[str, str]]
) -> Optional[str]:
    if plugin.input_ports >= 2:
        by_port = parents_by_port.get(node_id, {})
        if "left" not in by_port or "right" not in by_port:
            return f"{plugin.display_name} requires both a left and a right input to be connected."
        return None
    if plugin.input_ports > 0 and not parents.get(node_id):
        return f"{plugin.display_name} requires a connected input."
    return None


def _resolve_source_data(
    node_def: NodeDefinition, request: PipelineRequest, resolve_reference: Optional[ResolveReference]
) -> Optional[tuple[str, Any]]:
    config = node_def.config or {}

    data_reference_id = config.get("data_reference_id") or request.data_reference_id
    if data_reference_id and resolve_reference is not None:
        cached = resolve_reference(data_reference_id)
        if cached is not None:
            return ("parsed", cached)

    csv_text = config.get("csv_data")
    if csv_text is None and node_def.type == "read_csv":
        csv_text = request.csv_data
    if csv_text is not None:
        return ("csv_text", csv_text)

    return None
