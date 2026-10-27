
import io

import openpyxl
import pytest

from app.csv_io.parser import parse_csv
from app.data_cache import data_reference_cache
from app.engine.executor import DAGExecutor
from app.engine.registry import build_registry
from app.schemas.pipeline import EdgeDefinition, NodeDefinition, PipelineRequest

# A deliberately mixed dataset: numbers, strings, an empty cell (null), an ISO date, and
# booleans. Covers every DataType the parser can infer, so type-specific node behaviour
# (numeric filter, date filter, fill_missing on a string column, ...) is reachable.
SAMPLE_CSV = (
    "id,name,subject,score,grade_date,active\n"
    "1,Alice,Math,85,2024-01-01,true\n"
    "2,Bob,Math,42,2024-01-02,false\n"
    "3,Charlie,Science,90,2024-01-03,true\n"
    "4,Diana,Science,35,2024-01-04,false\n"
    "5,Eve,,77,2024-01-05,true\n"
    "6,Frank,Math,95,2024-01-06,true\n"
)

# Second dataset for the other side of a join: matching keys on 1 and 2, an extra key (3) that
# only exists on the left, and an extra key (4) that only exists on the right. So an INNER
# join gives 2 rows, LEFT gives 3, RIGHT gives 3, FULL gives 4 — every join type is
# distinguishable from the others by row count alone.
SAMPLE_LEFT_CSV = "id,name\n1,Alice\n2,Bob\n3,Cara\n"
SAMPLE_RIGHT_CSV = "id,city\n1,Rome\n2,Oslo\n4,Oslo\n"


@pytest.fixture
def registry():
    return build_registry()


@pytest.fixture
def executor(registry):
    """An executor wired exactly like routers/pipeline.py's get_executor().

    The resolve_reference callable is the part that matters: without it, every source node
    fails with "No CSV data available" regardless of what the pipeline config says, which is
    precisely the "no node works" class of bug these tests are meant to catch. resolve_raw
    (the upload bytes) is wired too, for the same reason — it's what read_xlsx's sheet_name
    needs to re-parse the requested sheet.
    """
    return DAGExecutor(
        registry,
        resolve_reference=data_reference_cache.get,
        resolve_raw=data_reference_cache.get_raw,
    )


@pytest.fixture
def sample_frame():
    """The SAMPLE_CSV parsed into a real FluxDataFrame, as a source node would produce."""
    return parse_csv(SAMPLE_CSV)


@pytest.fixture
def sample_ref(executor):
    """A data_reference_id for SAMPLE_CSV, the way /api/data/upload would hand it out."""
    return data_reference_cache.put(parse_csv(SAMPLE_CSV))


@pytest.fixture
def left_ref(executor):
    return data_reference_cache.put(parse_csv(SAMPLE_LEFT_CSV))


@pytest.fixture
def right_ref(executor):
    return data_reference_cache.put(parse_csv(SAMPLE_RIGHT_CSV))


@pytest.fixture
def xlsx_ref(executor):
    """A two-sheet workbook uploaded the way /api/data/upload stores it.

    Deliberately has more than one sheet: the first sheet is what an upload with no
    sheet_name resolves to, and picking a different sheet on the read_xlsx node is a
    user-facing feature (PLAN.md §6) that needs a second sheet to be testable at all.

    Stored with raw=..., exactly as the upload endpoint does — the executor can only honour a
    node's sheet_name if the original bytes are still in the cache.
    """
    return data_reference_cache.put(parse_xlsx_workbook(), raw=xlsx_bytes())


def parse_xlsx_workbook() -> "object":
    """Builds the two-sheet XLSX used by xlsx_ref and the read_xlsx tests."""
    workbook = _two_sheet_workbook()
    buffer = io.BytesIO()
    workbook.save(buffer)
    from app.csv_io.xlsx_io import parse_xlsx

    return parse_xlsx(buffer.getvalue())


def xlsx_bytes() -> bytes:
    """Raw XLSX bytes for the same two-sheet workbook, for upload-endpoint tests."""
    buffer = io.BytesIO()
    _two_sheet_workbook().save(buffer)
    return buffer.getvalue()


def _two_sheet_workbook() -> "openpyxl.Workbook":
    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "Sheet1"
    for row in [["id", "name", "amount"], [1, "Alice", 10], [2, "Bob", 20], [3, "Cara", 30]]:
        first.append(row)

    second = workbook.create_sheet("Sheet2")
    for row in [["name", "city"], ["Alice", "Rome"], ["Bob", "Oslo"]]:
        second.append(row)
    return workbook


def node(node_id: str, node_type: str, config: dict | None = None) -> NodeDefinition:
    return NodeDefinition(id=node_id, type=node_type, config=config or {})


def edge(source: str, target: str, port: str | None = None) -> EdgeDefinition:
    return EdgeDefinition(source_node_id=source, target_node_id=target, target_port=port)


def run_pipeline(executor: DAGExecutor, nodes, edges, **kwargs) -> "object":
    """Execute a pipeline described with node()/edge() helpers and return the ExecutionResult."""
    return executor.execute(PipelineRequest(nodes=list(nodes), edges=list(edges), **kwargs))


def source_node(ref: str, node_id: str = "src", node_type: str = "read_csv", **config) -> NodeDefinition:
    """A source node bound to an already-uploaded file, matching what UploadZone builds."""
    return node(node_id, node_type, {"data_reference_id": ref, **config})


def run_chain(executor: DAGExecutor, specs, source_ref: str, source_type: str = "read_csv"):
    """Run `specs` — a list of (node_id, node_type, config) — chained after one source node.

    Returns (result, node_ids) where node_ids are the generated ids in pipeline order, so a
    test can assert on a specific stage's result without repeating the wiring.
    """
    nodes = [source_node(source_ref, "n0", source_type)]
    edges = []
    previous = "n0"
    for index, (node_id, node_type, config) in enumerate(specs, start=1):
        nodes.append(node(node_id, node_type, config))
        edges.append(edge(previous, node_id))
        previous = node_id
    return run_pipeline(executor, nodes, edges), [n[0] for n in specs]
