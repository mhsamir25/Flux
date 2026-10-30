"""AGGREGATE-stage tests: group_by_aggregate and pivot, chained off a real source.

Aggregation is where the pipeline stops being a row-for-row transform, so it is also where
the two nodes can most easily lose or misreport data: group_by collapses groups, pivot
reshapes them, and both derive their output column names from a naming convention
(`{column}_{function.lower()}`) that every downstream node has to agree on. These tests run
both nodes through the executor on parsed data and check the numbers against values computed
by hand, plus the shape contract the rest of the pipeline depends on.
"""
import pytest

from app.nodes.base import SchemaValidationError
from tests.conftest import edge, node, run_pipeline, source_node


def run_aggregate(executor, ref, node_type, config, target="a"):
    return run_pipeline(
        executor,
        [node("src", "read_csv", {"data_reference_id": ref}), node(target, node_type, config)],
        [edge("src", target)],
    )


# --- group_by_aggregate ---------------------------------------------------------------

def test_group_by_average_per_group(executor, sample_ref):
    """Math(85,42,95) = 74, Science(90,35) = 62.5, History(77) = 77."""
    result = run_aggregate(executor, sample_ref, "group_by_aggregate", {
        "group_column": "subject",
        "aggregations": [{"column": "score", "function": "AVERAGE"}],
    })
    node_result = result.node_results["a"]
    assert node_result.success is True, node_result.error_message
    rows = {row["subject"]: row["score_average"] for row in node_result.preview_data}
    assert rows == {"Math": 74, "Science": 62.5, None: 77}
    assert node_result.total_row_count == 3


@pytest.mark.parametrize(
    "function,expected",
    [
        ("SUM", {"Math": 222, "Science": 125, None: 77}),
        ("AVERAGE", {"Math": 74, "Science": 62.5, None: 77}),
        ("MIN", {"Math": 42, "Science": 35, None: 77}),
        ("MAX", {"Math": 95, "Science": 90, None: 77}),
    ],
)
def test_every_numeric_aggregation_matches_hand_calculation(executor, sample_ref, function, expected):
    result = run_aggregate(executor, sample_ref, "group_by_aggregate", {
        "group_column": "subject",
        "aggregations": [{"column": "score", "function": function}],
    })
    node_result = result.node_results["a"]
    assert node_result.success is True, node_result.error_message
    rows = {row["subject"]: row[f"score_{function.lower()}"] for row in node_result.preview_data}
    assert rows == expected


def test_group_by_count_counts_rows_in_each_group(executor):
    """COUNT is "how many rows are in this group", not "how many non-null values".

    Regression test: it used to map onto pandas' null-skipping "count" aggregation, so the
    group 'a' below (2 rows, one of them null) reported 1 — while this node's own Excel export
    is COUNTIF, which counts rows. The chart and the generated formula disagreed.
    """
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("g,v\na,1\na,\nb,3\nb,4\n"))
    result = run_aggregate(executor, ref, "group_by_aggregate", {
        "group_column": "g",
        "aggregations": [{"column": "v", "function": "COUNT"}],
    })
    rows = {row["g"]: row["v_count"] for row in result.node_results["a"].preview_data}
    assert rows == {"a": 2, "b": 2}


def test_group_by_count_distinct_counts_unique_values(executor):
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("g,v\na,1\na,1\na,2\nb,9\n"))
    result = run_aggregate(executor, ref, "group_by_aggregate", {
        "group_column": "g",
        "aggregations": [{"column": "v", "function": "COUNT_DISTINCT"}],
    })
    rows = {row["g"]: row["v_count_distinct"] for row in result.node_results["a"].preview_data}
    assert rows == {"a": 2, "b": 1}


def test_group_by_emits_named_output_columns_for_each_aggregation(executor, sample_ref):
    result = run_aggregate(executor, sample_ref, "group_by_aggregate", {
        "group_column": "subject",
        "aggregations": [
            {"column": "score", "function": "AVERAGE"},
            {"column": "score", "function": "MAX"},
            {"column": "name", "function": "COUNT"},
        ],
    })
    node_result = result.node_results["a"]
    assert node_result.output_schema.column_names() == [
        "subject", "score_average", "score_max", "name_count",
    ]


def test_grouped_output_is_immediately_usable_by_a_sort_node(executor, sample_ref):
    """The canonical aggregation -> ordering handoff, including the renamed output column."""
    result = run_pipeline(
        executor,
        [
            node("src", "read_csv", {"data_reference_id": sample_ref}),
            node("g", "group_by_aggregate", {
                "group_column": "subject",
                "aggregations": [{"column": "score", "function": "AVERAGE"}],
            }),
            node("s", "sort", {"column": "score_average", "direction": "DESC"}),
        ],
        [edge("src", "g"), edge("g", "s")],
    )
    node_result = result.node_results["s"]
    assert node_result.success is True, node_result.error_message
    assert [row["subject"] for row in node_result.preview_data] == [None, "Math", "Science"]


def test_group_by_keeps_rows_whose_group_key_is_null(executor):
    """A missing group value is still a group — dropping it would lose the user's data."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("g,v\na,1\n,5\nb,3\n"))
    result = run_aggregate(executor, ref, "group_by_aggregate", {
        "group_column": "g",
        "aggregations": [{"column": "v", "function": "SUM"}],
    })
    assert result.node_results["a"].total_row_count == 3


def test_group_by_rejects_an_unknown_group_column(executor, sample_ref):
    result = run_aggregate(executor, sample_ref, "group_by_aggregate", {
        "group_column": "nope", "aggregations": [{"column": "score", "function": "SUM"}],
    })
    assert result.node_results["a"].success is False
    assert "nope" in result.node_results["a"].error_message


def test_group_by_rejects_an_unknown_aggregation_function(executor, sample_ref):
    result = run_aggregate(executor, sample_ref, "group_by_aggregate", {
        "group_column": "subject", "aggregations": [{"column": "score", "function": "MEDIAN"}],
    })
    assert result.node_results["a"].success is False
    assert "MEDIAN" in result.node_results["a"].error_message


def test_group_by_infers_the_output_schema_before_execution(sample_frame):
    """Schema inference runs without data, so it must not depend on execution happening."""
    from app.nodes.aggregate.group_by_aggregate import GroupByAggregateNode

    schema = GroupByAggregateNode().infer_output_schema(sample_frame.schema, {
        "group_column": "subject",
        "aggregations": [{"column": "score", "function": "AVERAGE"}],
    })
    assert schema.column_names() == ["subject", "score_average"]
    assert schema.get_column("score_average").type.value == "NUMBER"
    assert schema.get_column("subject").type.value == "STRING"


# --- pivot -----------------------------------------------------------------------------

def test_pivot_reshapes_rows_into_one_column_per_distinct_key_value(executor):
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv(
        "region,quarter,revenue\n"
        "North,Q1,10\nNorth,Q2,20\n"
        "South,Q1,30\nSouth,Q2,\n"
    ))
    result = run_aggregate(executor, ref, "pivot", {
        "row_column": "region", "column_column": "quarter",
        "value_column": "revenue", "aggregate_function": "SUM",
    })
    node_result = result.node_results["a"]
    assert node_result.success is True, node_result.error_message
    assert node_result.output_schema.column_names() == ["region", "Q1", "Q2"]
    assert [row["region"] for row in node_result.preview_data] == ["North", "South"]
    assert node_result.preview_data[1] == {"region": "South", "Q1": 30, "Q2": 0}


def test_pivot_keeps_rows_whose_key_values_are_missing(executor):
    """Nothing may be silently dropped, on either axis.

    Regression test: pivot_table defaults to dropna=True for both index and columns, so a row
    with a blank category vanished with no error and no warning — the revenue 3 below simply
    disappeared. group_by_aggregate already passed dropna=False, so the two aggregate nodes
    disagreed about whether a null key is data or noise. It is data.
    """
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("row,c,val\nr1,x,1\n,x,2\nr2,,3\nr2,x,4\n"))
    result = run_aggregate(executor, ref, "pivot", {
        "row_column": "row", "column_column": "c",
        "value_column": "val", "aggregate_function": "SUM",
    })
    node_result = result.node_results["a"]
    assert node_result.success is True, node_result.error_message

    # The row with no category survives as its own row, and the category-less value is kept in
    # a readable "(blank)" column rather than a column literally named "nan".
    assert node_result.output_schema.column_names() == ["row", "x", "(blank)"]
    rows = {row["row"]: row for row in node_result.preview_data}
    assert set(rows) == {"r1", "r2", None}
    assert rows["r2"]["x"] == 4 and rows["r2"]["(blank)"] == 3
    assert rows[None]["x"] == 2

    # And no input value went missing: 1 + 2 + 3 + 4 all accounted for.
    total = sum(v for row in node_result.preview_data for k, v in row.items() if k != "row" and v is not None)
    assert total == 10


def test_pivot_output_feeds_a_chart_node(executor):
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("r,c,v\na,x,1\na,y,2\nb,x,3\n"))
    result = run_pipeline(
        executor,
        [
            node("src", "read_csv", {"data_reference_id": ref}),
            node("p", "pivot", {
                "row_column": "r", "column_column": "c",
                "value_column": "v", "aggregate_function": "SUM",
            }),
            node("chart", "bar_chart", {"x_column": "r", "y_column": "x"}),
        ],
        [edge("src", "p"), edge("p", "chart")],
    )
    chart_result = result.node_results["chart"]
    assert chart_result.success is True, chart_result.error_message
    assert chart_result.output_schema.column_names() == ["r", "x", "y"]


def test_pivot_rejects_missing_column_config(executor, sample_ref):
    result = run_aggregate(executor, sample_ref, "pivot", {"row_column": "subject"})
    assert result.node_results["a"].success is False
    assert result.node_results["a"].error_message


def test_pivot_infer_output_schema_documents_that_it_is_a_lower_bound(sample_frame):
    """The real output columns only exist post-execution; inference returns what it can."""
    from app.nodes.aggregate.pivot import PivotNode

    schema = PivotNode().infer_output_schema(sample_frame.schema, {
        "row_column": "subject", "column_column": "name",
        "value_column": "score", "aggregate_function": "SUM",
    })
    assert schema.column_names() == ["subject"]


def test_group_by_infer_output_schema_rejects_duplicate_output_names(sample_frame):
    """Two identical column/function pairs would produce one column twice."""
    from app.nodes.aggregate.group_by_aggregate import GroupByAggregateNode

    with pytest.raises(SchemaValidationError, match="Duplicate output column"):
        GroupByAggregateNode().infer_output_schema(sample_frame.schema, {
            "group_column": "subject",
            "aggregations": [
                {"column": "score", "function": "SUM"},
                {"column": "score", "function": "SUM"},
            ],
        })
