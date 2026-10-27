import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.engine.executor import DAGExecutor, ExportError
from app.engine.registry import build_registry
from app.schemas.pipeline import EdgeDefinition, NodeDefinition, PipelineRequest

import pandas as pd


@pytest.fixture
def executor():
    return DAGExecutor(build_registry())


def _edge(source, target, port=None):
    return EdgeDefinition(source_node_id=source, target_node_id=target, target_port=port)


# --- linear pipeline -------------------------------------------------------------

def test_linear_pipeline_end_to_end(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "age", "operator": ">", "value": "25"}),
        NodeDefinition(id="n3", type="sort", config={"column": "age", "direction": "DESC"}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="name,age\nAlice,30\nBob,20\nCarol,40")

    result = executor.execute(request)

    assert result.node_results["n1"].success
    assert result.node_results["n1"].total_row_count == 3
    assert result.node_results["n2"].total_row_count == 2
    n3 = result.node_results["n3"]
    assert n3.success
    assert [r["name"] for r in n3.preview_data] == ["Carol", "Alice"]
    assert n3.output_schema.column_names() == ["name", "age"]


def test_no_edges_single_source_node(executor):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    request = PipelineRequest(nodes=nodes, edges=[], csv_data="x\n1\n2")
    result = executor.execute(request)
    assert result.node_results["n1"].success
    assert result.node_results["n1"].total_row_count == 2


def test_empty_pipeline(executor):
    request = PipelineRequest(nodes=[], edges=[])
    result = executor.execute(request)
    assert result.node_results == {}


# --- cycle detection ---------------------------------------------------------------

def test_cycle_is_isolated_and_rest_of_pipeline_still_runs(executor):
    nodes = [
        NodeDefinition(id="a", type="filter", config={"column": "x", "operator": ">", "value": "0"}),
        NodeDefinition(id="b", type="sort", config={"column": "x"}),
        NodeDefinition(id="c", type="limit_rows", config={"count": 5}),
        NodeDefinition(id="d", type="read_csv", config={}),
        NodeDefinition(id="e", type="limit_rows", config={"count": 1}),
    ]
    edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a"), _edge("d", "e")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="x\n1\n2\n3")

    result = executor.execute(request)

    for node_id in ("a", "b", "c"):
        r = result.node_results[node_id]
        assert not r.success
        assert "cycle" in r.error_message
        assert node_id in r.error_message or "a, b, c" in r.error_message
    assert result.node_results["d"].success
    assert result.node_results["e"].success


# --- failing middle node / cascading skip -------------------------------------------

def test_failing_middle_node_skips_downstream(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "missing_col", "operator": ">", "value": "1"}),
        NodeDefinition(id="n3", type="sort", config={"column": "age"}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="name,age\nAlice,30")

    result = executor.execute(request)

    assert result.node_results["n1"].success
    n2 = result.node_results["n2"]
    assert not n2.success
    assert not n2.skipped
    n3 = result.node_results["n3"]
    assert not n3.success
    assert n3.skipped
    assert "Upstream node failed" in n3.error_message


# --- required-input check -----------------------------------------------------------

def test_unconnected_transform_node_fails_clearly(executor):
    nodes = [NodeDefinition(id="n1", type="filter", config={"column": "x", "operator": ">", "value": "1"})]
    request = PipelineRequest(nodes=nodes, edges=[])
    result = executor.execute(request)
    assert not result.node_results["n1"].success
    assert "requires a connected input" in result.node_results["n1"].error_message


def test_join_missing_one_side_fails_clearly(executor):
    nodes = [
        NodeDefinition(id="left", type="read_csv", config={"csv_data": "id\n1"}),
        NodeDefinition(id="joined", type="join", config={"left_key": "id", "right_key": "id", "join_type": "INNER"}),
    ]
    edges = [_edge("left", "joined", port="left")]
    request = PipelineRequest(nodes=nodes, edges=edges)
    result = executor.execute(request)
    assert not result.node_results["joined"].success
    assert "left and a right" in result.node_results["joined"].error_message


def test_unregistered_node_type_fails_clearly(executor):
    nodes = [NodeDefinition(id="n1", type="not_a_real_node_type", config={})]
    request = PipelineRequest(nodes=nodes, edges=[])
    result = executor.execute(request)
    assert not result.node_results["n1"].success
    assert "Unknown node type" in result.node_results["n1"].error_message


def test_malformed_edge_to_unknown_node_is_dropped_not_fatal(executor):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    edges = [_edge("n1", "does_not_exist")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="x\n1")
    result = executor.execute(request)
    assert result.node_results["n1"].success


# --- join with two independent sources ------------------------------------------------

def test_join_pipeline_with_two_independent_sources(executor):
    nodes = [
        NodeDefinition(id="left", type="read_csv", config={"csv_data": "id,name\n1,Alice\n2,Bob"}),
        NodeDefinition(id="right", type="read_csv", config={"csv_data": "id,dept\n1,Eng\n3,HR"}),
        NodeDefinition(id="joined", type="join", config={"left_key": "id", "right_key": "id", "join_type": "LEFT"}),
    ]
    edges = [_edge("left", "joined", port="left"), _edge("right", "joined", port="right")]
    request = PipelineRequest(nodes=nodes, edges=edges)

    result = executor.execute(request)

    assert result.node_results["left"].total_row_count == 2
    assert result.node_results["right"].total_row_count == 2
    joined = result.node_results["joined"]
    assert joined.success
    assert joined.total_row_count == 2
    records = {r["name"]: r["dept"] for r in joined.preview_data}
    assert records["Alice"] == "Eng"
    assert records["Bob"] is None


def test_data_reference_id_resolves_via_injected_resolver():
    schema = DataSchema(columns=[Column(name="x", type=DataType.NUMBER)])
    cached_df = FluxDataFrame(schema=schema, df=pd.DataFrame({"x": [1, 2, 3]}), total_row_count=3)

    def resolver(ref_id):
        return cached_df if ref_id == "abc123" else None

    executor = DAGExecutor(build_registry(), resolve_reference=resolver)
    nodes = [NodeDefinition(id="n1", type="read_xlsx", config={"data_reference_id": "abc123"})]
    request = PipelineRequest(nodes=nodes, edges=[])

    result = executor.execute(request)

    assert result.node_results["n1"].success
    assert result.node_results["n1"].total_row_count == 3


def test_missing_data_reference_id_fails_clearly():
    executor = DAGExecutor(build_registry(), resolve_reference=lambda ref_id: None)
    nodes = [NodeDefinition(id="n1", type="read_csv", config={"data_reference_id": "nonexistent"})]
    request = PipelineRequest(nodes=nodes, edges=[])
    result = executor.execute(request)
    assert not result.node_results["n1"].success


# --- target_node_id partial execution --------------------------------------------------

def test_target_node_id_truncates_execution(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "age", "operator": ">", "value": "0"}),
        NodeDefinition(id="n3", type="sort", config={"column": "age"}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    request = PipelineRequest(
        nodes=nodes, edges=edges, csv_data="name,age\nAlice,30", target_node_id="n2",
    )
    result = executor.execute(request)
    assert set(result.node_results.keys()) == {"n1", "n2"}


def test_target_node_id_not_found_runs_everything(executor):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    request = PipelineRequest(nodes=nodes, edges=[], csv_data="x\n1", target_node_id="does_not_exist")
    result = executor.execute(request)
    assert result.node_results["n1"].success


# --- row-level error reporting (convert_type hook) ---------------------------------------

def test_convert_type_row_errors_reported_on_success(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="convert_type", config={"column": "val", "target_type": "NUMBER"}),
    ]
    edges = [_edge("n1", "n2")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="val\n10\nabc\n20")

    result = executor.execute(request)

    n2 = result.node_results["n2"]
    assert n2.success  # coercion failure doesn't fail the whole node
    assert n2.error_row_indices == [1]


def test_filter_node_has_no_row_errors(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "age", "operator": ">", "value": "0"}),
    ]
    edges = [_edge("n1", "n2")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="age\n1\n2")
    result = executor.execute(request)
    assert result.node_results["n2"].error_row_indices is None


# --- error message translation ----------------------------------------------------------

def test_generic_exception_gets_plain_english_translation(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="fill_missing", config={"column": "missing", "strategy": "fixed", "fixed_value": "0"}),
    ]
    edges = [_edge("n1", "n2")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="age\n1\n2")
    result = executor.execute(request)
    n2 = result.node_results["n2"]
    assert not n2.success
    assert n2.error_message  # some translated message present


# --- execute_for_export ------------------------------------------------------------------

def test_execute_for_export_returns_full_untruncated_dataframe(executor):
    header = "id,value\n"
    rows = "\n".join(f"{i},{i * 2}" for i in range(150))  # more than the 100-row preview cap
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    request = PipelineRequest(nodes=nodes, edges=[], csv_data=header + rows, target_node_id="n1")

    flux_df = executor.execute_for_export(request)

    assert flux_df.total_row_count == 150
    assert len(flux_df.df) == 150  # the full frame, not preview(100)


def test_execute_for_export_requires_target_node_id(executor):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    request = PipelineRequest(nodes=nodes, edges=[], csv_data="x\n1")
    with pytest.raises(ExportError, match="target_node_id"):
        executor.execute_for_export(request)


def test_execute_for_export_unknown_node_id_raises(executor):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    request = PipelineRequest(nodes=nodes, edges=[], csv_data="x\n1", target_node_id="does_not_exist")
    with pytest.raises(ExportError, match="not found"):
        executor.execute_for_export(request)


def test_execute_for_export_failed_node_raises_with_error_message(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "missing_col", "operator": ">", "value": "1"}),
    ]
    edges = [_edge("n1", "n2")]
    request = PipelineRequest(nodes=nodes, edges=edges, csv_data="age\n1\n2", target_node_id="n2")
    with pytest.raises(ExportError, match="missing_col"):
        executor.execute_for_export(request)


def test_execute_for_export_reflects_full_pipeline_transform(executor):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "age", "operator": ">", "value": "25"}),
    ]
    edges = [_edge("n1", "n2")]
    request = PipelineRequest(
        nodes=nodes, edges=edges, csv_data="name,age\nAlice,30\nBob,20", target_node_id="n2",
    )

    flux_df = executor.execute_for_export(request)

    assert list(flux_df.df["name"]) == ["Alice"]
