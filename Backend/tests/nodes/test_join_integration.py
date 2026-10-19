import pytest

from app.nodes.base import SchemaValidationError
from tests.conftest import edge, node, run_pipeline, source_node


def run_join(executor, left_ref, right_ref, join_type, left_key="id", right_key="id", node_id="j"):
    return run_pipeline(
        executor,
        [
            source_node(left_ref, "l", "read_csv"),
            source_node(right_ref, "r", "read_csv"),
            node(node_id, "join", {
                "left_key": left_key, "right_key": right_key, "join_type": join_type,
            }),
        ],
        [edge("l", node_id, "left"), edge("r", node_id, "right")],
    )


@pytest.mark.parametrize(
    "join_type,expected_rows",
    [("INNER", 2), ("LEFT", 3), ("RIGHT", 3), ("FULL", 4)],
)
def test_every_join_type_produces_the_right_number_of_rows(
    executor, left_ref, right_ref, join_type, expected_rows
):
    result = run_join(executor, left_ref, right_ref, join_type)
    node_result = result.node_results["j"]
    assert node_result.success is True, node_result.error_message
    assert node_result.total_row_count == expected_rows


def test_inner_join_keeps_only_matching_keys(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "INNER")
    rows = {row["id"]: row["city"] for row in result.node_results["j"].preview_data}
    assert rows == {1: "Rome", 2: "Oslo"}


def test_left_join_keeps_unmatched_left_rows_with_nulls_on_the_right(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "LEFT")
    rows = {row["id"]: row["city"] for row in result.node_results["j"].preview_data}
    assert rows == {1: "Rome", 2: "Oslo", 3: None}


def test_right_join_keeps_unmatched_right_rows(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "RIGHT")
    cities = {row["city"] for row in result.node_results["j"].preview_data}
    assert cities == {"Rome", "Oslo"}


def test_full_join_keeps_rows_from_both_sides(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "FULL")
    rows = result.node_results["j"].preview_data
    assert len(rows) == 4
    assert {row["id"] for row in rows} == {1, 2, 3, 4}


def test_joining_on_columns_with_different_names(executor):
    """left.id to right.person_id — the two key columns must both survive, unsuffixed."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    left = data_reference_cache.put(parse_csv("id,name\n1,Alice\n2,Bob\n"))
    right = data_reference_cache.put(parse_csv("person_id,city\n1,Rome\n3,Oslo\n"))
    result = run_join(executor, left, right, "INNER", left_key="id", right_key="person_id")
    node_result = result.node_results["j"]
    assert node_result.success is True, node_result.error_message
    assert node_result.output_schema.column_names() == ["id", "name", "person_id", "city"]
    assert [row["name"] for row in node_result.preview_data] == ["Alice"]


def test_overlapping_non_key_columns_are_suffixed_and_usable_downstream(executor):
    """The schema must say name_left/name_right exactly as the data does, or the column
    picker downstream offers names that don't exist in the data."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    left = data_reference_cache.put(parse_csv("id,name\n1,Alice\n"))
    right = data_reference_cache.put(parse_csv("id,name,score\n1,Ally,99\n"))
    result = run_join(executor, left, right, "INNER")
    node_result = result.node_results["j"]
    assert node_result.output_schema.column_names() == ["id", "name_left", "name_right", "score"]
    assert node_result.preview_data[0]["name_left"] == "Alice"
    assert node_result.preview_data[0]["name_right"] == "Ally"


def test_joined_output_is_immediately_usable_by_a_transform_node(executor, left_ref, right_ref):
    result = run_pipeline(
        executor,
        [
            source_node(left_ref, "l", "read_csv"),
            source_node(right_ref, "r", "read_csv"),
            node("j", "join", {"left_key": "id", "right_key": "id", "join_type": "LEFT"}),
            node("t", "filter", {"column": "name", "operator": "=", "value": "Cara"}),
        ],
        [edge("l", "j", "left"), edge("r", "j", "right"), edge("j", "t")],
    )
    node_result = result.node_results["t"]
    assert node_result.success is True, node_result.error_message
    assert [row["name"] for row in node_result.preview_data] == ["Cara"]


def test_join_requires_both_inputs_connected(executor, left_ref):
    """A join with one cable plugged in must say so, not crash on a missing parent."""
    result = run_pipeline(
        executor,
        [
            source_node(left_ref, "l", "read_csv"),
            node("j", "join", {"left_key": "id", "right_key": "id", "join_type": "INNER"}),
        ],
        [edge("l", "j", "left")],
    )
    node_result = result.node_results["j"]
    assert node_result.success is False
    assert "right" in node_result.error_message.lower()


def test_join_reports_an_unknown_join_type(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "CROSS")
    node_result = result.node_results["j"]
    assert node_result.success is False
    assert "CROSS" in node_result.error_message


def test_join_reports_a_key_that_does_not_exist_on_its_own_side(executor, left_ref, right_ref):
    result = run_join(executor, left_ref, right_ref, "INNER", left_key="nope", right_key="id")
    node_result = result.node_results["j"]
    assert node_result.success is False
    assert "nope" in node_result.error_message


def test_join_output_is_json_safe_when_the_right_side_has_no_match(executor, left_ref, right_ref):
    """Unmatched rows in a LEFT/FULL join produce nulls — they must serialize as null, not NaN,
    or the whole execute response becomes unparseable for the frontend (see the matrix test)."""
    result = run_join(executor, left_ref, right_ref, "LEFT")
    for record in result.node_results["j"].preview_data:
        for value in record.values():
            assert not (isinstance(value, float) and value != value)


def test_join_infers_its_schema_from_both_sides_via_the_reserved_config_key(left_ref):
    """infer_output_schema only receives one schema; the right one arrives as _right_schema."""
    from app.nodes.join.join_node import JoinNode

    from app.csv_io.parser import parse_csv

    left, right = parse_csv("id,name\n1,Alice\n"), parse_csv("id,city\n1,Rome\n")
    schema = JoinNode().infer_output_schema(
        left.schema, {"_right_schema": right.schema, "left_key": "id", "right_key": "id", "join_type": "INNER"}
    )
    assert schema.column_names() == ["id", "name", "city"]


def test_join_schema_inference_without_a_right_schema_is_a_schema_error():
    from app.nodes.join.join_node import JoinNode

    from app.csv_io.parser import parse_csv

    with pytest.raises(SchemaValidationError, match="left and a right"):
        JoinNode().infer_output_schema(
            parse_csv("id,name\n1,Alice\n").schema,
            {"left_key": "id", "right_key": "id", "join_type": "INNER"},
        )


def test_join_can_feed_a_join(executor):
    """Three sources, two joins — the deepest graph the app has to support."""
    from app.csv_io.parser import parse_csv
    from app.data_cache import data_reference_cache

    a = data_reference_cache.put(parse_csv("id,name\n1,Alice\n2,Bob\n"))
    b = data_reference_cache.put(parse_csv("id,city\n1,Rome\n2,Oslo\n"))
    c = data_reference_cache.put(parse_csv("id,score\n1,10\n2,20\n"))
    result = run_pipeline(
        executor,
        [
            source_node(a, "a", "read_csv"),
            source_node(b, "b", "read_csv"),
            source_node(c, "c", "read_csv"),
            node("j1", "join", {"left_key": "id", "right_key": "id", "join_type": "INNER"}),
            node("j2", "join", {"left_key": "id", "right_key": "id", "join_type": "INNER"}),
        ],
        [
            edge("a", "j1", "left"), edge("b", "j1", "right"),
            edge("j1", "j2", "left"), edge("c", "j2", "right"),
        ],
    )
    node_result = result.node_results["j2"]
    assert node_result.success is True, node_result.error_message
    assert node_result.total_row_count == 2
    assert node_result.output_schema.column_names() == ["id", "name", "city", "score"]


def test_join_cannot_be_connected_to_itself_and_only_accepts_two_inputs(executor, left_ref):
    from app.engine.registry import build_registry

    plugin = build_registry().get("join")
    assert plugin.input_ports == 2
    assert plugin.output_ports == 1

    result = run_pipeline(
        executor,
        [source_node(left_ref, "l", "read_csv"),
         node("j", "join", {"left_key": "id", "right_key": "id", "join_type": "INNER"})],
        [edge("j", "j", "left")],
    )
    assert result.node_results["j"].success is False
