"""SOURCE-stage tests: read_csv and read_xlsx as the app actually invokes them.

The source stage is where the whole pipeline either starts or dies, and it has one
app-specific property the unit tests in tests/nodes/test_read_csv.py don't model: in the
real app the file's bytes never travel with the execute request. The frontend uploads once
via POST /api/data/upload, gets a data_reference_id back, and every later execute call
carries only that id (UploadZone.jsx sets it on the source node's own config). So these
tests drive the source nodes through DAGExecutor with a data_reference_id and a real cache
behind them, which is the only path a user's data can take in production.
"""
import pytest

from app.csv_io.parser import parse_csv
from app.data_cache import data_reference_cache
from app.nodes.base import SchemaValidationError
from tests.conftest import SAMPLE_CSV, edge, node, run_pipeline, source_node, xlsx_bytes

from app.csv_io.xlsx_io import parse_xlsx


# --- read_csv ---------------------------------------------------------------------

def test_read_csv_resolves_data_from_a_cached_reference_id(executor, sample_ref):
    """The app's normal CSV path: upload once, execute many times by reference id."""
    result = run_pipeline(executor, [source_node(sample_ref, "src", "read_csv")], [])
    node_result = result.node_results["src"]

    assert node_result.success is True
    assert node_result.total_row_count == 6
    assert node_result.output_schema.column_names() == ["id", "name", "subject", "score", "grade_date", "active"]
    assert [row["name"] for row in node_result.preview_data][:2] == ["Alice", "Bob"]


def test_read_csv_accepts_raw_text_on_the_request(executor):
    """The documented no-cache fallback (PipelineRequest.csv_data) must still work."""
    result = run_pipeline(executor, [node("src", "read_csv", {})], [], csv_data=SAMPLE_CSV)
    assert result.node_results["src"].success is True
    assert result.node_results["src"].total_row_count == 6


def test_read_csv_accepts_raw_text_on_its_own_config(executor):
    """Per-node csv_data is the documented override for multi-source pipelines."""
    result = run_pipeline(executor, [node("src", "read_csv", {"csv_data": SAMPLE_CSV})], [])
    assert result.node_results["src"].success is True
    assert result.node_results["src"].total_row_count == 6


def test_read_csv_fails_cleanly_when_no_data_was_ever_supplied(executor):
    """A canvas with a Read CSV node and no upload must show a per-node error, not a 500."""
    result = run_pipeline(executor, [node("src", "read_csv", {})], [])
    node_result = result.node_results["src"]
    assert node_result.success is False
    assert "CSV" in node_result.error_message
    assert node_result.preview_data is None


def test_read_csv_fails_cleanly_on_an_expired_reference_id(executor):
    """data_reference_id cache entries expire after a TTL (§11); a miss must be a node error.

    This is the single most common real-world cause of "every node on my canvas suddenly
    turned red": the guest session's upload aged out of the two-hour cache.
    """
    result = run_pipeline(
        executor, [node("src", "read_csv", {"data_reference_id": "expired-id"})], []
    )
    assert result.node_results["src"].success is False
    assert result.node_results["src"].error_message


def test_read_csv_reports_unparseable_input_as_a_node_error(executor):
    result = run_pipeline(executor, [node("src", "read_csv", {"csv_data": ""})], [])
    # An empty document is not an error — it's an empty, valid table.
    assert result.node_results["src"].success is True
    assert result.node_results["src"].total_row_count == 0


def test_two_read_csv_nodes_can_carry_two_different_files(executor, left_ref, right_ref):
    """The join case: two independent sources, one file each, both via the same request."""
    result = run_pipeline(
        executor,
        [source_node(left_ref, "a", "read_csv"), source_node(right_ref, "b", "read_csv")],
        [],
    )
    assert result.node_results["a"].output_schema.column_names() == ["id", "name"]
    assert result.node_results["b"].output_schema.column_names() == ["id", "city"]


# --- read_xlsx --------------------------------------------------------------------

def test_read_xlsx_resolves_data_from_a_cached_reference_id(executor, xlsx_ref):
    """XLSX has no raw-text path at all, so the cached reference id is the ONLY way in."""
    result = run_pipeline(executor, [source_node(xlsx_ref, "src", "read_xlsx")], [])
    node_result = result.node_results["src"]

    assert node_result.success is True
    assert node_result.total_row_count == 3
    assert node_result.output_schema.column_names() == ["id", "name", "amount"]


def test_read_xlsx_runs_type_inference_like_csv(executor, xlsx_ref):
    """Excel's own cell typing must not be trusted blindly (PLAN.md §6/§11)."""
    result = run_pipeline(executor, [source_node(xlsx_ref, "src", "read_xlsx")], [])
    schema = result.node_results["src"].output_schema
    assert schema.get_column("id").type.value == "NUMBER"
    assert schema.get_column("name").type.value == "STRING"
    assert schema.get_column("amount").type.value == "NUMBER"


def test_read_xlsx_node_executes_directly_with_injected_bytes():
    """The node's own contract: bytes arrive under the reserved _xlsx_bytes config key."""
    from app.nodes.source.read_xlsx import ReadXlsxNode

    frame = ReadXlsxNode().execute_source({"_xlsx_bytes": xlsx_bytes()})
    assert frame.total_row_count == 3
    assert frame.schema.column_names() == ["id", "name", "amount"]


def test_read_xlsx_without_bytes_raises_a_clear_error():
    from app.nodes.source.read_xlsx import ReadXlsxNode

    with pytest.raises(SchemaValidationError, match="XLSX"):
        ReadXlsxNode().execute_source({})


def test_read_xlsx_honours_its_sheet_name_config(executor, xlsx_ref):
    """Regression test: the node's sheet_name used to be ignored entirely.

    The executor short-circuited to the frame parsed at upload time, so a multi-sheet
    workbook always loaded sheet 1 no matter what the config panel said. The cache now keeps
    the upload bytes and the executor re-parses when a source node asks it to
    (NodePlugin.requires_reparse).
    """
    result = run_pipeline(
        executor, [source_node(xlsx_ref, "src", "read_xlsx", sheet_name="Sheet2")], []
    )
    node_result = result.node_results["src"]
    assert node_result.success is True
    assert node_result.output_schema.column_names() == ["name", "city"]
    assert [row["city"] for row in node_result.preview_data] == ["Rome", "Oslo"]


def test_read_xlsx_with_no_sheet_name_still_loads_the_first_sheet(executor, xlsx_ref):
    """The default path must be untouched by the re-parse behaviour above."""
    result = run_pipeline(executor, [source_node(xlsx_ref, "src", "read_xlsx")], [])
    assert result.node_results["src"].output_schema.column_names() == ["id", "name", "amount"]


def test_read_xlsx_reports_a_bad_sheet_name_instead_of_falling_back(executor, xlsx_ref):
    """A sheet that doesn't exist is a user error worth surfacing, not a silent sheet 1."""
    result = run_pipeline(
        executor, [source_node(xlsx_ref, "src", "read_xlsx", sheet_name="Nope")], []
    )
    node_result = result.node_results["src"]
    assert node_result.success is False
    assert "Nope" in node_result.error_message


def test_read_xlsx_falls_back_to_the_cached_frame_when_raw_bytes_were_not_kept():
    """A cache entry written without raw bytes still works; it just can't re-parse.

    Best-effort degradation: better to return the sheet that was uploaded than to fail the
    node outright, and the parser's own error surfaces if a re-parse isn't possible.
    """
    from app.csv_io.xlsx_io import parse_xlsx
    from app.data_cache import data_reference_cache
    from app.engine.executor import DAGExecutor
    from app.engine.registry import build_registry

    reference_id = data_reference_cache.put(parse_xlsx(xlsx_bytes()))
    executor = DAGExecutor(build_registry(), resolve_reference=data_reference_cache.get)
    result = run_pipeline(
        executor, [source_node(reference_id, "src", "read_xlsx", sheet_name="Sheet2")], []
    )
    node_result = result.node_results["src"]
    assert node_result.success is True
    assert node_result.output_schema.column_names() == ["id", "name", "amount"]


def test_read_xlsx_can_still_select_a_sheet_at_upload_time():
    """The upload endpoint's sheet_name form field is the one path that does work today.

    Worth pinning: it is the only reason sheet selection is not completely missing, and it
    also documents how far the behaviour is from what the config panel promises.
    """
    frame = parse_xlsx(xlsx_bytes(), sheet_name="Sheet2")
    assert frame.schema.column_names() == ["name", "city"]

    reference_id = data_reference_cache.put(frame)
    from tests.conftest import run_pipeline as _run
    from app.engine.executor import DAGExecutor
    from app.engine.registry import build_registry

    result = _run(
        DAGExecutor(build_registry(), resolve_reference=data_reference_cache.get),
        [source_node(reference_id, "src", "read_xlsx")],
        [],
    )
    assert result.node_results["src"].output_schema.column_names() == ["name", "city"]


def test_read_xlsx_rejects_an_unknown_sheet_name_at_the_parser_level():
    from app.csv_io.parser import FileParsingError

    with pytest.raises(FileParsingError, match="not found"):
        parse_xlsx(xlsx_bytes(), sheet_name="Nope")


def test_read_xlsx_feeds_downstream_transform_nodes(executor, xlsx_ref):
    """The full source -> processor hop for XLSX, which is where a broken schema shows up."""
    result = run_pipeline(
        executor,
        [
            source_node(xlsx_ref, "src", "read_xlsx"),
            node("t", "filter", {"column": "amount", "operator": ">", "value": "10"}),
        ],
        [edge("src", "t")],
    )
    assert result.node_results["t"].success is True
    assert result.node_results["t"].total_row_count == 2
    assert [row["name"] for row in result.node_results["t"].preview_data] == ["Bob", "Cara"]


# --- shared source behaviour -------------------------------------------------------

def test_source_node_schemas_are_typed_and_nonnullable_safe(executor, sample_ref):
    """A source's own output_schema is what feeds every downstream column picker."""
    result = run_pipeline(executor, [source_node(sample_ref, "src", "read_csv")], [])
    columns = {c.name: c.type.value for c in result.node_results["src"].output_schema.columns}
    assert columns == {
        "id": "NUMBER", "name": "STRING", "subject": "STRING",
        "score": "NUMBER", "grade_date": "DATE", "active": "BOOLEAN",
    }


def test_source_nodes_have_no_input_ports_so_nothing_needs_to_connect(executor, sample_ref):
    """The canvas must be able to leave a source unconnected without the engine objecting."""
    from app.engine.registry import build_registry

    registry = build_registry()
    assert registry.get("read_csv").input_ports == 0
    assert registry.get("read_xlsx").input_ports == 0

    result = run_pipeline(executor, [source_node(sample_ref, "src", "read_csv")], [])
    assert result.node_results["src"].success is True


def test_two_sources_in_one_request_do_not_share_data(executor, left_ref, right_ref):
    """Guards against the executor's pipeline-level data fallback leaking across sources."""
    result = run_pipeline(
        executor,
        [source_node(left_ref, "a", "read_csv"), node("b", "read_csv", {})],
        [],
        data_reference_id=left_ref,
    )
    assert result.node_results["a"].success is True
    assert result.node_results["b"].success is True
    assert result.node_results["a"].output_schema.column_names() == ["id", "name"]
    assert result.node_results["b"].output_schema.column_names() == ["id", "name"]


def test_pipeline_level_reference_id_is_the_fallback_for_a_bare_source_node(executor, left_ref):
    """No per-node config at all — the §11 documented fallback still has to work."""
    result = run_pipeline(executor, [node("src", "read_csv", {})], [], data_reference_id=left_ref)
    assert result.node_results["src"].success is True
    assert result.node_results["src"].total_row_count == 3
