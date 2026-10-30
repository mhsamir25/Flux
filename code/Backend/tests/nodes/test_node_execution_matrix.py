"""Every registered node type, run through the real executor, checked against the
invariants the app depends on.

Why a matrix instead of one test per node: the per-node modules in tests/nodes/ already
cover each node's happy path in isolation. What they cannot catch is the class of bug the
app actually reports — "the node shows up in the sidebar but the canvas node glows red."
That failure is almost never inside the node's own logic; it is one of the seams:

  * the node was never registered, or registered under an id the registry can't find
    (engine/registry.py) — the sidebar renders it, every execution says "Unknown node type";
  * the source feeding it never resolved, so it was skipped as a downstream casualty;
  * the node succeeded but produced an output that violates the contract the rest of the
    app relies on: schema columns that don't match the DataFrame's columns, a
    total_row_count that doesn't match the data, or preview_data that isn't JSON-safe.

So this module drives every node type the way the app does — through DAGExecutor.execute
with a data_reference_id, exactly like the frontend's UploadZone + ReactFlowCanvas do — and
asserts the invariants uniformly. One parametrized case per node type, so a failure names
the node that broke rather than aborting the whole suite.
"""
import math

import pytest

from app.csv_io.parser import parse_csv
from app.data_cache import data_reference_cache
from app.engine.executor import DAGExecutor
from app.engine.registry import build_registry
from tests.conftest import SAMPLE_CSV, edge, node, run_pipeline, source_node

# One case per registered node: (node_type, config, needs_second_source).
# Configs are exactly what the frontend's config panel can produce from the node's own
# get_config_schema() field list — the keys here are the FieldSchema keys, nothing invented.
NODE_CASES = [
    ("read_csv", {}, False),
    ("read_xlsx", {"sheet_name": "Sheet1"}, False),
    ("filter", {"column": "score", "operator": "≥", "value": "50"}, False),
    ("sort", {"column": "score", "direction": "DESC"}, False),
    ("select_columns", {"columns": ["name", "score"]}, False),
    ("rename_column", {"mappings": [{"from": "name", "to": "student"}]}, False),
    ("limit_rows", {"count": 3}, False),
    ("remove_duplicates", {"columns": ["subject"]}, False),
    ("fill_missing", {"column": "subject", "strategy": "fixed", "fixed_value": "Unknown"}, False),
    ("convert_type", {"column": "score", "target_type": "STRING"}, False),
    ("add_calculated_column", {"new_column_name": "double", "expression": "score * 2"}, False),
    ("group_by_aggregate", {"group_column": "subject", "aggregations": [{"column": "score", "function": "AVERAGE"}]}, False),
    ("pivot", {"row_column": "subject", "column_column": "name", "value_column": "score", "aggregate_function": "SUM"}, False),
    ("join", {"left_key": "id", "right_key": "id", "join_type": "INNER"}, True),
    ("bar_chart", {"x_column": "name", "y_column": "score"}, False),
    ("line_chart", {"x_column": "grade_date", "y_column": "score"}, False),
    ("pie_chart", {"x_column": "subject", "y_column": "score"}, False),
    ("data_table", {"columns": ["name", "score"]}, False),
]

NODE_IDS = [case[0] for case in NODE_CASES]


def run_case(executor, sample_ref, left_ref, right_ref, xlsx_ref, node_type, config,
             needs_second_source):
    """Runs one node case and returns (ExecutionResult, result_key_of_the_node_under_test)."""
    if needs_second_source:
        result = run_pipeline(
            executor,
            [
                source_node(left_ref, "left", "read_csv"),
                source_node(right_ref, "right", "read_csv"),
                node("join", node_type, config),
            ],
            [edge("left", "join", "left"), edge("right", "join", "right")],
        )
        return result, "join"

    if node_type in ("read_csv", "read_xlsx"):
        # Source nodes ARE the node under test here, so they get no upstream edge and no
        # downstream node — same shape the canvas has right after an upload.
        is_xlsx = node_type == "read_xlsx"
        ref = xlsx_ref if is_xlsx else sample_ref
        result = run_pipeline(executor, [source_node(ref, "src", node_type, **config)], [])
        return result, "src"

    result = run_pipeline(
        executor,
        [source_node(sample_ref, "src", "read_csv"), node("n1", node_type, config)],
        [edge("src", "n1")],
    )
    return result, "n1"


# --- the matrix itself ------------------------------------------------------------

@pytest.mark.parametrize("node_type,config,needs_second_source", NODE_CASES, ids=NODE_IDS)
def test_node_runs_successfully_in_a_real_pipeline(executor, sample_ref, left_ref, right_ref,
                                                  xlsx_ref, node_type, config, needs_second_source):
    """The node's own result must be success=True with no error message.

    A failure here is the "node is broken in the app" report verbatim: whatever the node
    does, it has to survive being executed by the engine.
    """
    result, target = run_case(executor, sample_ref, left_ref, right_ref, xlsx_ref,
                              node_type, config, needs_second_source)
    node_result = result.node_results[target]
    assert node_result.success, f"{node_type} failed: {node_result.error_message}"
    assert node_result.skipped is False
    assert node_result.error_message is None


@pytest.mark.parametrize("node_type,config,needs_second_source", NODE_CASES, ids=NODE_IDS)
def test_node_output_schema_matches_its_data(executor, sample_ref, left_ref, right_ref,
                                             xlsx_ref, node_type, config, needs_second_source):
    """output_schema.columns must line up with the actual DataFrame columns, in order.

    The config panel and the preview table both render column pickers from
    output_schema (§13). If the schema drifts from the real data, a column that visibly
    exists in the preview table cannot be selected — which reads to a user as "this node is
    broken" even though the data underneath is fine.
    """
    result, target = run_case(executor, sample_ref, left_ref, right_ref, xlsx_ref,
                              node_type, config, needs_second_source)
    node_result = result.node_results[target]
    schema_names = node_result.output_schema.column_names()
    record_keys = list(node_result.preview_data[0].keys()) if node_result.preview_data else schema_names
    assert schema_names == record_keys, (
        f"{node_type}: schema {schema_names} does not match data columns {record_keys}"
    )


@pytest.mark.parametrize("node_type,config,needs_second_source", NODE_CASES, ids=NODE_IDS)
def test_node_reports_a_consistent_row_count(executor, sample_ref, left_ref, right_ref,
                                             xlsx_ref, node_type, config, needs_second_source):
    """total_row_count must be the real row count of the node's output.

    The replay feature (§14) animates a per-node row-count badge straight off this field, so
    a wrong count makes the replay animation misreport what the pipeline did.
    """
    result, target = run_case(executor, sample_ref, left_ref, right_ref, xlsx_ref,
                              node_type, config, needs_second_source)
    node_result = result.node_results[target]
    assert node_result.total_row_count is not None
    if node_result.total_row_count <= 100:
        assert len(node_result.preview_data) == node_result.total_row_count
    else:
        assert len(node_result.preview_data) == 100, "preview must stay capped at 100 rows"


@pytest.mark.parametrize("node_type,config,needs_second_source", NODE_CASES, ids=NODE_IDS)
def test_node_preview_data_is_json_safe(executor, sample_ref, left_ref, right_ref,
                                        xlsx_ref, node_type, config, needs_second_source):
    """preview_data must survive JSON serialization with no NaN/Infinity leaking out.

    FastAPI's JSON encoder emits a bare `NaN` token for a float NaN, which is not valid
    JSON — axios/JSON.parse on the frontend then rejects the whole execute response, so
    EVERY node on the canvas stops updating at once even though the server "succeeded".
    One node emitting a NaN is enough to take down the live preview for a whole pipeline.
    """
    result, target = run_case(executor, sample_ref, left_ref, right_ref, xlsx_ref,
                              node_type, config, needs_second_source)
    for row_index, record in enumerate(result.node_results[target].preview_data):
        for key, value in record.items():
            assert not _is_non_json_number(value), (
                f"{node_type}: row {row_index} column {key!r} is {value!r}, which is not "
                "valid JSON and will break the frontend's parse of the whole response"
            )


def _is_non_json_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    return False


# --- the seams the matrix depends on ---------------------------------------------

def test_every_expected_node_type_is_registered():
    """The catalogue the sidebar renders must be the set the executor can actually run.

    A node class that exists but was never added to build_registry() is invisible in the
    sidebar; a registry entry under a misspelled id makes every execution of that node fail
    with "Unknown node type" — both silent until someone tries to use the node.
    """
    registered = {plugin.id for plugin in build_registry().all()}
    assert registered == set(NODE_IDS), (
        f"registry/case-list mismatch: only in registry={registered - set(NODE_IDS)}, "
        f"only in test cases={set(NODE_IDS) - registered}"
    )


def test_registry_lookup_uses_the_same_id_the_catalogue_advertises():
    """GET /api/nodes advertises plugin.id; NodeDefinition.type is matched against it.

    These are the same string across the whole app, so a mismatch is fatal to whichever
    node is affected while every other node keeps working — the "only some nodes work" bug.
    """
    registry = build_registry()
    for plugin in registry.all():
        assert registry.get(plugin.id) is plugin


def test_unknown_node_type_fails_only_that_node(executor):
    """One bad node type must not take the rest of the pipeline down with it."""
    good_ref = data_reference_cache.put(parse_csv(SAMPLE_CSV))
    result = run_pipeline(
        executor,
        [
            source_node(good_ref, "src", "read_csv"),
            node("bad", "not_a_real_node", {}),
            node("after", "data_table", {"columns": ["name"]}),
        ],
        [edge("src", "bad"), edge("bad", "after")],
    )
    assert result.node_results["src"].success is True
    assert result.node_results["bad"].success is False
    assert "not_a_real_node" in result.node_results["bad"].error_message
    assert result.node_results["after"].skipped is True


def test_every_node_survives_being_run_without_a_resolver_hooked_up():
    """A source with no resolvable data must fail cleanly, not raise out of execute().

    The executor is constructed with a data_reference_cache resolver in the router, but a
    cache miss (expired TTL, wrong id) still has to produce a per-node error — an exception
    escaping execute() would surface as a 500 and blank the whole canvas's results.
    """
    resolverless = DAGExecutor(build_registry())
    result = run_pipeline(
        resolverless,
        [node("src", "read_csv", {}), node("t", "filter", {"column": "score", "operator": ">", "value": "1"})],
        [edge("src", "t")],
        csv_data=SAMPLE_CSV,
    )
    assert result.node_results["src"].success is True
    assert result.node_results["t"].success is True

    missing = run_pipeline(
        resolverless,
        [node("src", "read_csv", {"data_reference_id": "does-not-exist"}), node("t", "filter", {})],
        [edge("src", "t")],
    )
    assert missing.node_results["src"].success is False
    assert missing.node_results["src"].error_message
    assert missing.node_results["t"].skipped is True
