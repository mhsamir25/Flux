"""SINK-stage tests: the three chart nodes and the data table.

Output nodes are the end of the pipeline, so "not working" here looks different from the
other stages: there is no downstream node to go red, the user just sees an empty preview or
a chart that never draws. That makes the pass-through contract the important thing to pin
down — a chart node must hand its input's data forward unchanged, and data_table must narrow
to exactly the columns it was configured with, in the order it was given them.
"""
import pytest

from app.nodes.base import SchemaValidationError
from tests.conftest import edge, node, run_pipeline, source_node

CHART_NODES = ["bar_chart", "line_chart", "pie_chart"]


def run_output(executor, sample_ref, node_type, config, target="out"):
    return run_pipeline(
        executor,
        [source_node(sample_ref, "src", "read_csv"), node(target, node_type, config)],
        [edge("src", target)],
    )


# --- chart nodes -----------------------------------------------------------------------

@pytest.mark.parametrize("node_type", CHART_NODES)
def test_chart_nodes_pass_their_input_through_untouched(executor, sample_ref, node_type):
    """Charts render in the browser from preview_data + config; the backend just forwards.

    If a chart node altered the data (dropped a column, reordered rows), every chart in the
    app would be subtly wrong while still reporting success.
    """
    config = {"x_column": "name", "y_column": "score"}
    result = run_output(executor, sample_ref, node_type, config)
    node_result = result.node_results["out"]

    assert node_result.success is True, node_result.error_message
    assert node_result.total_row_count == 6
    assert node_result.output_schema.column_names() == ["id", "name", "subject", "score", "grade_date", "active"]
    assert [row["name"] for row in node_result.preview_data] == [
        "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
    ]


@pytest.mark.parametrize("node_type", CHART_NODES)
def test_chart_nodes_expose_the_columns_the_frontend_renders_with(executor, sample_ref, node_type):
    """The frontend reads the node's own config keys to pick axes, so all three charts must
    accept the same x_column/y_column/title/color contract."""
    plugin = __import__("app.engine.registry", fromlist=["build_registry"]).build_registry().get(node_type)
    keys = [field.key for field in plugin.get_config_schema()]
    assert keys == ["x_column", "y_column", "title", "color"]


@pytest.mark.parametrize("node_type", CHART_NODES)
def test_chart_columns_must_exist_in_the_upstream_data(executor, sample_ref, node_type):
    """A chart pointed at a column the upstream node dropped must fail, not draw nothing.

    Regression test: ChartNode.execute() is a pure pass-through and used to skip validation
    entirely, so this reported success and the frontend drew an empty chart with a green node.
    The node's infer_output_schema() has always raised for this config; DAGExecutor now
    consults it before execute().
    """
    result = run_output(executor, sample_ref, node_type, {"x_column": "name", "y_column": "nope"})
    node_result = result.node_results["out"]
    assert node_result.success is False
    assert "nope" in node_result.error_message


@pytest.mark.parametrize("node_type", CHART_NODES)
def test_chart_nodes_cannot_be_exported_as_excel_formulas(node_type):
    """§6/§8.1: charts have no formula equivalent, and the catalogue must say so up front so
    the formula panel greys out instead of failing at runtime."""
    from app.engine.registry import build_registry

    plugin = build_registry().get(node_type)
    assert plugin.formula_exportable is False
    assert plugin.to_excel_formula("Sheet1!A1:Z1000", {"x_column": "a", "y_column": "b"}) is None
    assert plugin.to_excel_formula_explanation({"x_column": "a", "y_column": "b"})


def test_chart_after_an_aggregate_gets_the_aggregated_columns(executor, sample_ref):
    """The most common real chart: group_by -> sort -> bar_chart, using renamed columns."""
    result = run_pipeline(
        executor,
        [
            source_node(sample_ref, "src", "read_csv"),
            node("g", "group_by_aggregate", {
                "group_column": "subject",
                "aggregations": [{"column": "score", "function": "AVERAGE"}],
            }),
            node("c", "bar_chart", {"x_column": "subject", "y_column": "score_average"}),
        ],
        [edge("src", "g"), edge("g", "c")],
    )
    chart_result = result.node_results["c"]
    assert chart_result.success is True, chart_result.error_message
    assert chart_result.output_schema.column_names() == ["subject", "score_average"]
    assert chart_result.total_row_count == 3


def test_chart_config_pointing_at_a_pre_aggregation_column_fails_clearly(executor, sample_ref):
    """After grouping, the original 'score' column no longer exists — the exact mistake a
    user makes when wiring up an aggregate -> chart chain, and one that used to render as a
    blank chart with a green node."""
    result = run_pipeline(
        executor,
        [
            source_node(sample_ref, "src", "read_csv"),
            node("g", "group_by_aggregate", {
                "group_column": "subject",
                "aggregations": [{"column": "score", "function": "AVERAGE"}],
            }),
            node("c", "bar_chart", {"x_column": "subject", "y_column": "score"}),
        ],
        [edge("src", "g"), edge("g", "c")],
    )
    assert result.node_results["c"].success is False


# --- data_table -----------------------------------------------------------------------

def test_data_table_narrows_to_the_configured_columns_in_order(executor, sample_ref):
    result = run_output(executor, sample_ref, "data_table", {"columns": ["score", "name"]})
    node_result = result.node_results["out"]
    assert node_result.success is True, node_result.error_message
    assert node_result.output_schema.column_names() == ["score", "name"]
    assert list(node_result.preview_data[0].keys()) == ["score", "name"]
    assert node_result.total_row_count == 6


def test_data_table_with_no_columns_shows_everything(executor, sample_ref):
    """rows_per_page is a frontend pagination hint and must not slice the server's data."""
    result = run_output(executor, sample_ref, "data_table", {"rows_per_page": 2})
    node_result = result.node_results["out"]
    assert node_result.success is True
    assert node_result.output_schema.column_names() == ["id", "name", "subject", "score", "grade_date", "active"]
    assert node_result.total_row_count == 6


def test_data_table_rejects_a_column_that_an_upstream_node_removed(executor, sample_ref):
    """Select Columns -> Data Table naming a column Select dropped is a classic wiring slip."""
    result = run_pipeline(
        executor,
        [
            source_node(sample_ref, "src", "read_csv"),
            node("s", "select_columns", {"columns": ["name", "score"]}),
            node("d", "data_table", {"columns": ["name", "subject"]}),
        ],
        [edge("src", "s"), edge("s", "d")],
    )
    node_result = result.node_results["d"]
    assert node_result.success is False
    assert "subject" in node_result.error_message


def test_data_table_is_a_pass_through_for_formula_generation(executor, sample_ref):
    """data_table wraps its input's formula unchanged — the terminal node of most pipelines."""
    from app.nodes.output.data_table import DataTableNode

    assert DataTableNode().to_excel_formula("Sheet1!A1:Z1000", {}) == "Sheet1!A1:Z1000"
    assert DataTableNode().formula_exportable is True


def test_output_nodes_declare_one_input_and_one_output_port():
    from app.engine.registry import build_registry

    registry = build_registry()
    for node_id in CHART_NODES + ["data_table"]:
        plugin = registry.get(node_id)
        assert plugin.input_ports == 1
        assert plugin.output_ports == 1
        assert plugin.category.value == "OUTPUT"


def test_output_node_schema_inference_rejects_a_missing_axis(sample_frame):
    from app.nodes.output._chart_base import ChartNode

    with pytest.raises(SchemaValidationError):
        ChartNode().infer_output_schema(sample_frame.schema, {"x_column": "name"})
