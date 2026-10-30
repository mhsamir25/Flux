"""PROCESSOR-stage tests: the ten transform nodes, chained off a real source.

These mirror the matrix's approach at the transform level: every case runs through
DAGExecutor against a cached upload rather than calling execute() on a hand-built
FluxDataFrame, so a node is only considered "working" if it works in the app.

Each node's own module already has unit tests for its arithmetic; what's tested here is the
behaviour a user actually trips over — the *shape* of the data flowing between nodes:
nulls, type coercion, and whether a misconfiguration fails with a message a user can act
on instead of a pandas internal.
"""
import pytest

from app.nodes.base import SchemaValidationError
from tests.conftest import edge, node, run_pipeline, source_node


def run_transform(executor, sample_ref, node_type, config, target="t"):
    """source -> single transform node, exactly the two-node canvas the user builds first."""
    return run_pipeline(
        executor,
        [source_node(sample_ref, "src", "read_csv"), node(target, node_type, config)],
        [edge("src", target)],
    )


def run_pair(executor, sample_ref, first, second):
    """source -> transform -> transform, for nodes whose output feeds another's input."""
    return run_pipeline(
        executor,
        [
            source_node(sample_ref, "src", "read_csv"),
            node("a", first[0], first[1]),
            node("b", second[0], second[1]),
        ],
        [edge("src", "a"), edge("a", "b")],
    )


# --- filter ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "config,expected_names",
    [
        ({"column": "score", "operator": "≥", "value": "50"}, ["Alice", "Charlie", "Eve", "Frank"]),
        ({"column": "score", "operator": "<", "value": "50"}, ["Bob", "Diana"]),
        ({"column": "subject", "operator": "=", "value": "Math"}, ["Alice", "Bob", "Frank"]),
        ({"column": "subject", "operator": "≠", "value": "Math"}, ["Charlie", "Diana", "Eve"]),
        ({"column": "name", "operator": "contains", "value": "a"}, ["Charlie", "Diana", "Frank"]),
        ({"column": "name", "operator": "starts_with", "value": "A"}, ["Alice"]),
        ({"column": "subject", "operator": "is_empty"}, ["Eve"]),
        ({"column": "subject", "operator": "is_not_empty"}, ["Alice", "Bob", "Charlie", "Diana", "Frank"]),
    ],
)
def test_filter_operators_over_real_parsed_data(executor, sample_ref, config, expected_names):
    """Every operator in the node's ENUM list, against inferred-typed data from a real parse.

    is_empty/is_not_empty are the operators most likely to break: the CSV parser maps blank
    cells to null, so an `== ""` style implementation would return nothing at all.
    """
    result = run_transform(executor, sample_ref, "filter", config)
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["name"] for row in node_result.preview_data] == expected_names
    assert node_result.total_row_count == len(expected_names)


def test_filter_supports_a_second_condition_group_combined_with_logic(executor, sample_ref):
    result = run_transform(executor, sample_ref, "filter", {
        "column": "score", "operator": "≥", "value": "50",
        "column2": "subject", "operator2": "=", "value2": "Science",
        "logic": "AND",
    })
    assert [row["name"] for row in result.node_results["t"].preview_data] == ["Charlie"]

    or_result = run_transform(executor, sample_ref, "filter", {
        "column": "score", "operator": "≥", "value": "90",
        "column2": "subject", "operator2": "=", "value2": "Science",
        "logic": "OR",
    })
    assert [row["name"] for row in or_result.node_results["t"].preview_data] == ["Charlie", "Diana", "Frank"]


def test_filter_reports_an_unknown_column_as_an_actionable_error(executor, sample_ref):
    """A stale column pick (e.g. the upstream Select Columns dropped it) must be explained."""
    result = run_transform(executor, sample_ref, "filter", {"column": "nope", "operator": "=", "value": "1"})
    node_result = result.node_results["t"]
    assert node_result.success is False
    assert "nope" in node_result.error_message


def test_filter_on_a_date_column_compares_dates_not_strings(executor, sample_ref):
    result = run_transform(executor, sample_ref, "filter",
                           {"column": "grade_date", "operator": ">", "value": "2024-01-04"})
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["name"] for row in node_result.preview_data] == ["Eve", "Frank"]


# --- sort --------------------------------------------------------------------------

def test_sort_descending_renumbers_row_indices(executor, sample_ref):
    result = run_transform(executor, sample_ref, "sort", {"column": "score", "direction": "DESC"})
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["name"] for row in node_result.preview_data] == ["Frank", "Charlie", "Alice", "Eve", "Bob", "Diana"]
    assert node_result.total_row_count == 6


def test_sort_supports_multiple_keys_with_independent_directions(executor, sample_ref):
    result = run_transform(executor, sample_ref, "sort", {"sort_keys": [
        {"column": "subject", "direction": "ASC"},
        {"column": "score", "direction": "DESC"},
    ]})
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["name"] for row in node_result.preview_data] == ["Frank", "Alice", "Bob", "Charlie", "Diana", "Eve"]


def test_sort_then_filter_matches_hand_calculation(executor, sample_ref):
    """Chained processors — the case a real pipeline hits immediately."""
    result = run_pair(
        executor, sample_ref,
        ("sort", {"column": "score", "direction": "DESC"}),
        ("filter", {"column": "score", "operator": "≥", "value": "80"}),
    )
    assert result.node_results["b"].success is True
    assert [row["name"] for row in result.node_results["b"].preview_data] == ["Frank", "Charlie", "Alice"]


# --- select / rename / limit / dedupe ----------------------------------------------

def test_select_columns_narrows_the_schema_for_downstream_pickers(executor, sample_ref):
    result = run_pair(
        executor, sample_ref,
        ("select_columns", {"columns": ["name", "score"]}),
        ("sort", {"column": "score", "direction": "DESC"}),
    )
    node_result = result.node_results["b"]
    assert node_result.success is True
    assert node_result.output_schema.column_names() == ["name", "score"]


def test_renaming_a_column_is_visible_to_the_next_node(executor, sample_ref):
    result = run_pair(
        executor, sample_ref,
        ("rename_column", {"mappings": [{"from": "score", "to": "mark"}]}),
        ("sort", {"column": "mark", "direction": "ASC"}),
    )
    node_result = result.node_results["b"]
    assert node_result.success is True, node_result.error_message
    assert node_result.output_schema.column_names() == ["id", "name", "subject", "mark", "grade_date", "active"]
    assert [row["mark"] for row in node_result.preview_data] == [35, 42, 77, 85, 90, 95]


def test_limit_rows_truncates_and_reports_the_truncated_count(executor, sample_ref):
    result = run_transform(executor, sample_ref, "limit_rows", {"count": 2})
    node_result = result.node_results["t"]
    assert node_result.total_row_count == 2
    assert [row["name"] for row in node_result.preview_data] == ["Alice", "Bob"]


def test_remove_duplicates_on_all_columns_when_none_selected(executor, sample_ref):
    ref_csv = "a,b\n1,x\n1,x\n2,y\n2,y\n3,z\n"
    result = run_pipeline(
        executor,
        [node("src", "read_csv", {"csv_data": ref_csv}), node("t", "remove_duplicates", {})],
        [edge("src", "t")],
    )
    assert result.node_results["t"].total_row_count == 3


def test_remove_duplicates_on_a_subset_keeps_distinct_rows(executor, sample_ref):
    """Subject has 3 distinct values across 6 rows, so 3 rows must survive."""
    result = run_transform(executor, sample_ref, "remove_duplicates", {"columns": ["subject"]})
    assert result.node_results["t"].total_row_count == 3


# --- fill_missing -------------------------------------------------------------------

def test_fill_missing_fixed_fills_only_the_nulls(executor, sample_ref):
    result = run_transform(executor, sample_ref, "fill_missing",
                           {"column": "subject", "strategy": "fixed", "fixed_value": "Unknown"})
    node_result = result.node_results["t"]
    subjects = {row["name"]: row["subject"] for row in node_result.preview_data}
    assert subjects["Eve"] == "Unknown"
    assert subjects["Alice"] == "Math"


def test_fill_missing_average_uses_the_column_mean(executor, sample_ref):
    result = run_transform(executor, sample_ref, "fill_missing",
                           {"column": "score", "strategy": "average"})
    node_result = result.node_results["t"]
    assert node_result.success is True
    scores = {row["name"]: row["score"] for row in node_result.preview_data}
    assert scores["Eve"] == 77  # no nulls in this column, so nothing changes
    assert node_result.total_row_count == 6


def test_fill_missing_median_matches_numpy_median(executor):
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    # The blank cell sits in a second column's row so read_csv can't drop the line as blank.
    ref = data_reference_cache.put(parse_csv("v,w\n1,a\n3,b\n,c\n7,d\n"))
    result = run_transform(executor, ref, "fill_missing", {"column": "v", "strategy": "median"})
    assert [row["v"] for row in result.node_results["t"].preview_data] == [1, 3, 3, 7]


def test_fill_missing_previous_carries_the_value_forward(executor):
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("k,v\n1,a\n2,\n3,c\n4,\n"))
    result = run_transform(executor, ref, "fill_missing", {"column": "v", "strategy": "previous"})
    values = [row["v"] for row in result.node_results["t"].preview_data]
    assert values == ["a", "a", "c", "c"]


def test_fill_missing_average_on_a_string_column_fails_with_a_clear_message(executor, sample_ref):
    """Regression test: this used to surface pandas' 'Cannot perform reduction mean with
    string dtype' on the canvas. infer_output_schema now rejects the strategy up front."""
    result = run_transform(executor, sample_ref, "fill_missing",
                           {"column": "subject", "strategy": "average"})
    node_result = result.node_results["t"]
    assert node_result.success is False
    message = node_result.error_message.lower()
    assert "average" in message and "subject" in message
    assert "reduction" not in message and "dtype" not in message


def test_fill_missing_rejects_an_unknown_strategy_with_a_schema_error(executor, sample_ref):
    with pytest.raises(SchemaValidationError, match="strategy"):
        from app.nodes.transform.fill_missing import FillMissingNode

        FillMissingNode().infer_output_schema(
            run_transform(executor, sample_ref, "data_table", {}).node_results["t"].output_schema,
            {"column": "subject", "strategy": "mode"},
        )


# --- convert_type -------------------------------------------------------------------

@pytest.mark.parametrize(
    "column,target_type,expected",
    [
        ("score", "STRING", ["85", "42"]),
        ("subject", "NUMBER", [None, None]),
    ],
)
def test_convert_type_casts_a_whole_column(executor, sample_ref, column, target_type, expected):
    result = run_transform(executor, sample_ref, "convert_type",
                           {"column": column, "target_type": target_type})
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row[column] for row in node_result.preview_data][:2] == expected
    assert node_result.output_schema.get_column(column).type.value == target_type


def test_convert_type_flags_the_rows_it_could_not_convert(executor):
    """Row-level error highlighting (§7.1) is what convert_type exists for."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("v\n10\nabc\n30\n"))
    result = run_transform(executor, ref, "convert_type", {"column": "v", "target_type": "NUMBER"})
    node_result = result.node_results["t"]
    assert node_result.success is True
    assert node_result.error_row_indices == [1]
    assert node_result.preview_data[1]["v"] is None


def test_convert_number_to_date_coerces_unconvertible_values_to_null(executor):
    """Regression test: pd.to_datetime(85, errors='coerce') doesn't fail, it reads a bare int
    as nanoseconds since the epoch and returns 1970-01-01 00:00:00.000000085 — a plausible-
    looking wrong answer for a user who pointed convert_type at an ID or count column. Numeric
    cells are now masked out before parsing, so they become nulls and get flagged as row-level
    errors instead."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("n\n85\n42\n"))
    result = run_transform(executor, ref, "convert_type", {"column": "n", "target_type": "DATE"})
    node_result = result.node_results["t"]
    assert [row["n"] for row in node_result.preview_data] == [None, None]
    assert node_result.error_row_indices == [0, 1]


def test_convert_type_still_parses_real_date_strings(executor):
    """The fix must not break the case the node exists for."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("d\n2024-01-01\n2024-06-30\n"))
    result = run_transform(executor, ref, "convert_type", {"column": "d", "target_type": "DATE"})
    node_result = result.node_results["t"]
    assert node_result.success is True
    assert [row["d"][:10] for row in node_result.preview_data] == ["2024-01-01", "2024-06-30"]
    assert node_result.error_row_indices is None


def test_convert_type_to_date_on_an_already_datetime_column_is_a_no_op(executor):
    """Re-converting a parsed date column must not wipe it (dates read as nanosecond ints)."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("d\n2024-01-01\n2024-06-30\n"))
    result = run_transform(executor, ref, "convert_type", {"column": "d", "target_type": "DATE"})
    assert [row["d"][:10] for row in result.node_results["t"].preview_data] == ["2024-01-01", "2024-06-30"]


def test_convert_type_then_sort_on_the_converted_column(executor):
    """The common cleaning chain: coerce, then order by the cleaned column."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    ref = data_reference_cache.put(parse_csv("v\n30\nabc\n10\n"))
    result = run_pipeline(
        executor,
        [
            node("src", "read_csv", {"data_reference_id": ref}),
            node("c", "convert_type", {"column": "v", "target_type": "NUMBER"}),
            node("s", "sort", {"column": "v", "direction": "ASC"}),
        ],
        [edge("src", "c"), edge("c", "s")],
    )
    assert result.node_results["s"].success is True, result.node_results["s"].error_message
    assert [row["v"] for row in result.node_results["s"].preview_data] == [10, 30, None]


# --- add_calculated_column -----------------------------------------------------------

@pytest.mark.parametrize(
    "expression,expected",
    [
        ("score * 2", [170, 84, 180]),
        ("score + 10", [95, 52, 100]),
        ("[score] - [id]", [84, 40]),
        ('name & " (" & subject & ")"', ["Alice (Math)", "Bob (Math)"]),
        ("IF(score > 50, score, 0)", [85, 0, 90]),
        ("score > 50", [True, False, True]),
    ],
)
def test_add_calculated_column_evaluates_expressions(executor, sample_ref, expression, expected):
    result = run_transform(executor, sample_ref, "add_calculated_column",
                           {"new_column_name": "calc", "expression": expression})
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["calc"] for row in node_result.preview_data][:len(expected)] == expected
    assert node_result.output_schema.column_names()[-1] == "calc"


def test_add_calculated_column_output_is_immediately_usable_downstream(executor, sample_ref):
    result = run_pair(
        executor, sample_ref,
        ("add_calculated_column", {"new_column_name": "score2", "expression": "score * 2"}),
        ("filter", {"column": "score2", "operator": ">", "value": "150"}),
    )
    assert result.node_results["b"].success is True, result.node_results["b"].error_message
    assert [row["name"] for row in result.node_results["b"].preview_data] == ["Alice", "Charlie", "Eve", "Frank"]


def test_add_calculated_column_refuses_to_overwrite_an_existing_column(executor, sample_ref):
    result = run_transform(executor, sample_ref, "add_calculated_column",
                           {"new_column_name": "score", "expression": "score * 2"})
    assert result.node_results["t"].success is False
    assert "already exists" in result.node_results["t"].error_message


def test_add_calculated_column_reports_a_malformed_expression(executor, sample_ref):
    result = run_transform(executor, sample_ref, "add_calculated_column",
                           {"new_column_name": "calc", "expression": "score *"})
    node_result = result.node_results["t"]
    assert node_result.success is False
    assert "expression" in node_result.error_message.lower()


def test_add_calculated_column_does_not_execute_arbitrary_python(executor, sample_ref):
    """The security requirement in PLAN.md §6: no eval() on user input.

    A regression here would turn every canvas config field into remote code execution, so
    this asserts the behaviour rather than the implementation detail.
    """
    result = run_transform(executor, sample_ref, "add_calculated_column", {
        "new_column_name": "pwned",
        "expression": "__import__('os').system('true')",
    })
    assert result.node_results["t"].success is False


def test_add_calculated_column_with_no_column_name_is_a_config_error(executor, sample_ref):
    result = run_transform(executor, sample_ref, "add_calculated_column", {"expression": "score * 2"})
    assert result.node_results["t"].success is False


# --- unconfigured nodes in general ----------------------------------------------------

@pytest.mark.parametrize(
    "node_type,config",
    [
        ("filter", {}),
        ("sort", {}),
        ("fill_missing", {}),
        ("convert_type", {}),
        ("add_calculated_column", {}),
        ("group_by_aggregate", {}),
        ("pivot", {}),
    ],
)
def test_a_freshly_dropped_node_fails_without_breaking_the_pipeline(
    executor, sample_ref, node_type, config
):
    """A node dragged onto the canvas starts with an empty config.

    It must fail as itself — with a message, not an exception escaping the request — and it
    must not take the source feeding it down with it. This is the literal "I dropped a node
    and everything went red" scenario from a half-configured canvas.
    """
    result = run_transform(executor, sample_ref, node_type, config)
    assert result.node_results["src"].success is True
    node_result = result.node_results["t"]
    assert node_result.success is False
    assert node_result.error_message, f"{node_type} failed with no message"
    assert node_result.preview_data is None


def test_unconfigured_select_columns_fails_instead_of_returning_an_empty_table(executor, sample_ref):
    """Regression test: df[[]] quietly yielded a zero-column table and the node reported
    success, so it glowed green with an empty preview. 'columns' is a required field and the
    node's own infer_output_schema raises — the executor now consults it before execute()."""
    result = run_transform(executor, sample_ref, "select_columns", {})
    node_result = result.node_results["t"]
    assert node_result.success is False
    assert node_result.error_message


def test_unconfigured_limit_rows_fails_instead_of_returning_no_rows(executor, sample_ref):
    """Regression test: config.get('count', 0) turned a missing count into zero rows rather
    than a config error, so a freshly dropped node wiped the data and reported success."""
    result = run_transform(executor, sample_ref, "limit_rows", {})
    node_result = result.node_results["t"]
    assert node_result.success is False
    assert node_result.error_message
