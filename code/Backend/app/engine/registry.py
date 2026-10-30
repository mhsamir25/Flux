"""NodeRegistry — explicit, in-memory registration of every NodePlugin.

GET /api/nodes serializes registry.all() into NodeCatalogueEntry objects; this is the single
endpoint the frontend sidebar and config panel are built against, so the registry is the
source of truth for "which node types exist" at runtime.
"""
from app.nodes.aggregate.group_by_aggregate import GroupByAggregateNode
from app.nodes.aggregate.pivot import PivotNode
from app.nodes.base import NodePlugin
from app.nodes.join.join_node import JoinNode
from app.nodes.output.bar_chart import BarChartNode
from app.nodes.output.data_table import DataTableNode
from app.nodes.output.line_chart import LineChartNode
from app.nodes.output.pie_chart import PieChartNode
from app.nodes.source.read_csv import ReadCsvNode
from app.nodes.source.read_xlsx import ReadXlsxNode
from app.nodes.transform.add_calculated_column import AddCalculatedColumnNode
from app.nodes.transform.convert_type import ConvertTypeNode
from app.nodes.transform.fill_missing import FillMissingNode
from app.nodes.transform.filter_node import FilterNode
from app.nodes.transform.limit_rows import LimitRowsNode
from app.nodes.transform.remove_duplicates import RemoveDuplicatesNode
from app.nodes.transform.rename_column import RenameColumnNode
from app.nodes.transform.select_columns import SelectColumnsNode
from app.nodes.transform.sort_node import SortNode


class NodeRegistry:
    def __init__(self):
        self._plugins: dict[str, NodePlugin] = {}

    def register(self, plugin: NodePlugin) -> None:
        self._plugins[plugin.id] = plugin

    def get(self, node_id: str) -> NodePlugin:
        if node_id not in self._plugins:
            raise KeyError(f"Node type '{node_id}' is not registered")
        return self._plugins[node_id]

    def all(self) -> list[NodePlugin]:
        return list(self._plugins.values())


def build_registry() -> NodeRegistry:
    """Explicit registration list, called once on app startup (main.py lifespan).

    Prefer this over decorator-based auto-discovery for a fixed, small set of 17 node
    types — it's more readable and avoids import-order surprises. Node plugins are added
    here one by one as they're implemented (PLAN.md Build Order step 5).
    """
    registry = NodeRegistry()
    registry.register(ReadCsvNode())
    registry.register(ReadXlsxNode())
    registry.register(FilterNode())
    registry.register(SortNode())
    registry.register(SelectColumnsNode())
    registry.register(RenameColumnNode())
    registry.register(LimitRowsNode())
    registry.register(RemoveDuplicatesNode())
    registry.register(FillMissingNode())
    registry.register(ConvertTypeNode())
    registry.register(AddCalculatedColumnNode())
    registry.register(GroupByAggregateNode())
    registry.register(PivotNode())
    registry.register(JoinNode())
    registry.register(BarChartNode())
    registry.register(LineChartNode())
    registry.register(PieChartNode())
    registry.register(DataTableNode())
    return registry


_registry_singleton: "NodeRegistry | None" = None


def get_registry() -> NodeRegistry:
    """FastAPI dependency: a lazily-built, process-wide shared NodeRegistry.

    A plain lazy singleton rather than routing everything through app.state — the registry is
    pure/stateless once built (no per-request mutation), so there's nothing app.state's request-
    scoped lifecycle actually buys here, and Depends(get_registry) is simpler to use/override
    in tests than threading `request: Request` through every route that needs it. main.py's
    lifespan still calls this once at startup (Phase 3's original intent: fail fast on a
    registration error at boot, not on a route's first request) — it just also happens to be
    the same object every route dependency gets afterward.
    """
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = build_registry()
    return _registry_singleton
