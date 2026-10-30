"""Whole-pipeline integration: source -> processor -> sink, and the engine behaviour the
frontend depends on.

The per-node modules in tests/nodes/ cover one node at a time and tests/test_executor.py
covers the graph algorithm. Neither covers the thing the user actually does: upload a file,
wire five nodes together, and watch the last one light up. That's what this module does,
using the onboarding pipeline from PLAN.md §14 as the reference case, plus the engine
features the canvas relies on (partial execution for live preview, cycle rejection,
skip-cascading, the 100-row preview cap, and full-row export).
"""
import pytest

from app.csv_io.parser import parse_csv
from app.data_cache import data_reference_cache
from app.engine.executor import ExportError
from tests.conftest import edge, node, run_pipeline, source_node, xlsx_bytes

# The onboarding pipeline, verbatim from Frontend/src/onboardingPipeline.js — the first thing
# every new user sees. If this chain breaks, the app looks broken on first load.
ONBOARDING_NODES = [
    node("n1", "read_csv", {}),
    node("n2", "filter", {"column": "Grade", "operator": "≥", "value": "50"}),
    node("n3", "group_by_aggregate", {
        "group_column": "Subject",
        "aggregations": [{"column": "Grade", "function": "AVERAGE"}],
    }),
    node("n4", "sort", {"column": "Grade_average", "direction": "DESC"}),
    node("n5", "bar_chart", {"x_column": "Subject", "y_column": "Grade_average"}),
]
ONBOARDING_EDGES = [edge("n1", "n2"), edge("n2", "n3"), edge("n3", "n4"), edge("n4", "n5")]
ONBOARDING_CSV = (
    "Name,Subject,Grade\n"
    "Alice,Math,85\nBob,Math,42\nCharlie,Science,90\nDiana,Science,35\n"
    "Eve,History,75\nFrank,Math,95\nGrace,Science,88\nHenry,History,60\nIvy,History,40\n"
)


def test_the_onboarding_pipeline_runs_end_to_end(executor):
    """First-load experience: every node green, terminal chart populated."""
    result = run_pipeline(executor, ONBOARDING_NODES, ONBOARDING_EDGES, csv_data=ONBOARDING_CSV)

    failures = {nid: r.error_message for nid, r in result.node_results.items() if not r.success}
    assert not failures, f"onboarding pipeline failed at: {failures}"

    # 9 rows, 6 of them scoring 50 or above.
    assert result.node_results["n2"].total_row_count == 6
    # Alice/Frank (Math, 85/95 -> 90), Charlie/Grace (Science, 90/88 -> 89), Eve/Henry (History, 75/60 -> 67.5).
    assert result.node_results["n3"].total_row_count == 3
    terminal = result.node_results["n5"]
    assert terminal.output_schema.column_names() == ["Subject", "Grade_average"]
    assert [row["Subject"] for row in terminal.preview_data] == ["Math", "Science", "History"]
    assert [row["Grade_average"] for row in terminal.preview_data] == [90, 89, 67.5]


def test_every_stage_of_the_onboarding_pipeline_reports_the_right_row_count(executor):
    """The replay feature animates these exact counts; a wrong one misleads the user."""
    result = run_pipeline(executor, ONBOARDING_NODES, ONBOARDING_EDGES, csv_data=ONBOARDING_CSV)
    counts = {nid: r.total_row_count for nid, r in result.node_results.items()}
    assert counts == {"n1": 9, "n2": 6, "n3": 3, "n4": 3, "n5": 3}


# --- partial execution / live preview -------------------------------------------------

@pytest.mark.parametrize("target,expected_done", [("n2", {"n1", "n2"}), ("n3", {"n1", "n2", "n3"}), ("n5", set())])
def test_target_node_id_stops_execution_at_that_node(executor, target, expected_done):
    """Live preview after every block runs the graph only up to the node being previewed."""
    result = run_pipeline(
        executor, ONBOARDING_NODES, ONBOARDING_EDGES,
        csv_data=ONBOARDING_CSV, target_node_id=target,
    )
    done = set(result.node_results)
    if expected_done:
        assert done == expected_done
    else:
        assert done == {"n1", "n2", "n3", "n4", "n5"}
    assert result.node_results[target].success is True


def test_partial_execution_still_reports_upstream_failures(executor):
    result = run_pipeline(
        executor,
        [node("n1", "read_csv", {}), node("n2", "filter", {"column": "ghost", "operator": "=", "value": "1"})],
        [edge("n1", "n2")],
        csv_data=ONBOARDING_CSV,
        target_node_id="n2",
    )
    assert result.node_results["n2"].success is False
    assert "ghost" in result.node_results["n2"].error_message


def test_preview_is_capped_at_100_rows_while_the_true_count_is_reported(executor):
    """§7.3: the canvas is told the real row count so it can say "showing 100 of N"."""
    big_csv = "n\n" + "".join(f"{i}\n" for i in range(250))
    result = run_pipeline(
        executor,
        [node("src", "read_csv", {"csv_data": big_csv}), node("t", "data_table", {})],
        [edge("src", "t")],
    )
    node_result = result.node_results["t"]
    assert node_result.total_row_count == 250
    assert len(node_result.preview_data) == 100


# --- failure propagation ---------------------------------------------------------------

def test_a_failing_middle_node_skips_everything_downstream(executor):
    result = run_pipeline(
        executor,
        [
            node("n1", "read_csv", {}),
            node("n2", "filter", {"column": "ghost", "operator": "=", "value": "1"}),
            node("n3", "sort", {"column": "score", "direction": "ASC"}),
            node("n4", "data_table", {}),
        ],
        [edge("n1", "n2"), edge("n2", "n3"), edge("n3", "n4")],
        csv_data=ONBOARDING_CSV,
    )
    assert result.node_results["n1"].success is True
    assert result.node_results["n2"].success is False
    for downstream in ("n3", "n4"):
        node_result = result.node_results[downstream]
        assert node_result.success is False
        assert node_result.skipped is True
        assert "Upstream" in node_result.error_message


def test_a_healthy_branch_of_a_diamond_still_runs(executor):
    """One broken input must not take out an unrelated branch of the same graph."""
    left_ref = data_reference_cache.put(parse_csv("id,name\n1,Alice\n"))
    right_ref = data_reference_cache.put(parse_csv("id,city\n1,Rome\n"))
    result = run_pipeline(
        executor,
        [
            source_node(left_ref, "l", "read_csv"),
            source_node(right_ref, "r", "read_csv"),
            node("bad", "join", {"left_key": "ghost", "right_key": "id", "join_type": "INNER"}),
            node("ok", "data_table", {"columns": ["name"]}),
        ],
        [edge("l", "bad", "left"), edge("r", "bad", "right"), edge("l", "ok")],
    )
    assert result.node_results["bad"].success is False
    assert result.node_results["ok"].success is True
    assert result.node_results["ok"].total_row_count == 1


def test_row_level_errors_survive_to_the_frontend_payload(executor):
    """error_row_indices is what drives the red-row highlighting in the preview table."""
    ref = data_reference_cache.put(parse_csv("v\n10\nnope\n30\n"))
    result = run_pipeline(
        executor,
        [node("src", "read_csv", {"data_reference_id": ref}),
         node("c", "convert_type", {"column": "v", "target_type": "NUMBER"})],
        [edge("src", "c")],
    )
    assert result.node_results["c"].error_row_indices == [1]


# --- cycles and malformed graphs -------------------------------------------------------

def test_a_cycle_is_reported_on_every_node_involved_and_leaves_the_rest_alone(executor, sample_ref):
    result = run_pipeline(
        executor,
        [
            source_node(sample_ref, "src", "read_csv"),
            node("a", "filter", {"column": "score", "operator": ">", "value": "1"}),
            node("b", "sort", {"column": "score", "direction": "ASC"}),
        ],
        [edge("src", "a"), edge("a", "b"), edge("b", "a")],
    )
    assert result.node_results["src"].success is True
    for cycle_node in ("a", "b"):
        assert result.node_results[cycle_node].success is False
        assert "cycle" in result.node_results[cycle_node].error_message.lower()
    assert "a" in result.node_results["b"].error_message


def test_a_transform_node_with_nothing_connected_to_it_is_reported_clearly(executor, sample_ref):
    result = run_pipeline(
        executor,
        [source_node(sample_ref, "src", "read_csv"),
         node("orphan", "filter", {"column": "score", "operator": ">", "value": "1"})],
        [],
    )
    node_result = result.node_results["orphan"]
    assert node_result.success is False
    assert "input" in node_result.error_message.lower()


def test_an_edge_referencing_a_missing_node_is_dropped_not_fatal(executor, sample_ref):
    result = run_pipeline(
        executor,
        [source_node(sample_ref, "src", "read_csv"),
         node("t", "data_table", {"columns": ["name"]})],
        [edge("src", "t"), edge("src", "ghost-node")],
    )
    assert result.node_results["t"].success is True


# --- export (the sink for the whole pipeline) ---------------------------------------------

def test_export_returns_the_full_row_set_not_the_capped_preview(executor):
    """§14: CSV export must not be built on the 100-row preview."""
    big_csv = "n\n" + "".join(f"{i}\n" for i in range(250))
    request_result = run_pipeline(
        executor,
        [node("src", "read_csv", {"csv_data": big_csv})],
        [],
    )
    assert len(request_result.node_results["src"].preview_data) == 100

    from app.schemas.pipeline import PipelineRequest

    frame = executor.execute_for_export(
        PipelineRequest(
            nodes=[node("src", "read_csv", {"csv_data": big_csv})],
            edges=[],
            target_node_id="src",
        )
    )
    assert len(frame.df) == 250


def test_export_of_a_failed_node_is_rejected_with_a_reason(executor):
    from app.schemas.pipeline import PipelineRequest

    with pytest.raises(ExportError, match="ghost"):
        executor.execute_for_export(
            PipelineRequest(
                nodes=[
                    node("src", "read_csv", {}),
                    node("t", "filter", {"column": "ghost", "operator": "=", "value": "1"}),
                ],
                edges=[edge("src", "t")],
                target_node_id="t",
                csv_data=ONBOARDING_CSV,
            )
        )


def test_export_without_a_target_node_is_rejected(executor):
    from app.schemas.pipeline import PipelineRequest

    with pytest.raises(ExportError, match="target_node_id"):
        executor.execute_for_export(PipelineRequest(nodes=[], edges=[]))


def test_export_sanitizes_formula_injection_on_the_way_out(executor):
    """§11/§16: a cell starting with =, +, - or @ is prefixed before it reaches Excel."""
    from app.schemas.pipeline import PipelineRequest
    from app.csv_io.parser import write_csv

    frame = executor.execute_for_export(
        PipelineRequest(
            nodes=[node("src", "read_csv", {"csv_data": "a\n=1+1\n@SUM(A1)\n-2\n"})],
            edges=[],
            target_node_id="src",
        )
    )
    exported = write_csv(frame.df)
    assert "'=1+1" in exported
    assert "'@SUM(A1)" in exported


# --- xlsx through the whole pipeline -------------------------------------------------------

def test_an_uploaded_xlsx_can_flow_all_the_way_to_a_chart(executor, xlsx_ref):
    result = run_pipeline(
        executor,
        [
            source_node(xlsx_ref, "src", "read_xlsx"),
            node("f", "filter", {"column": "amount", "operator": "≥", "value": "20"}),
            node("s", "sort", {"column": "amount", "direction": "DESC"}),
            node("c", "bar_chart", {"x_column": "name", "y_column": "amount"}),
        ],
        [edge("src", "f"), edge("f", "s"), edge("s", "c")],
    )
    failures = {nid: r.error_message for nid, r in result.node_results.items() if not r.success}
    assert not failures, f"xlsx pipeline failed at: {failures}"
    assert [row["name"] for row in result.node_results["c"].preview_data] == ["Cara", "Bob"]


def test_xlsx_bytes_survive_a_round_trip_through_the_parser():
    from app.csv_io.xlsx_io import parse_xlsx, write_xlsx

    frame = parse_xlsx(xlsx_bytes())
    assert frame.total_row_count == 3
    reparsed = parse_xlsx(write_xlsx(frame.df))
    assert reparsed.schema.column_names() == frame.schema.column_names()
    assert reparsed.total_row_count == 3
