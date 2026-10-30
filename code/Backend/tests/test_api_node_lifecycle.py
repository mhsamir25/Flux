"""HTTP-level tests for the node lifecycle: upload -> catalogue -> execute -> export.

Everything above this line tests the engine; the app's users never touch it. They upload a
file through POST /api/data/upload, pull the node palette from GET /api/nodes, and post the
canvas graph to POST /api/pipeline/execute — and the payload they send has a very specific
shape produced by Frontend/src/components/canvas/ReactFlowCanvas.jsx:

    {"nodes": [{"id", "type", "config"}], "edges": [{"source_node_id", "target_node_id",
     "target_port"}], "csv_data": ...}

These tests send exactly that shape over HTTP against the real FastAPI app, with no
Authorization header at all, because "it works as a guest" (§12) is itself a requirement —
and because a node that only works when the engine is called directly but not through the
router is precisely the kind of seam that produces "some nodes don't work in the app".
"""
import io

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.rate_limit import limiter
from tests.conftest import SAMPLE_CSV, xlsx_bytes

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    """All ASGI test requests share one synthetic client IP, so the process-wide limiter has
    to be reset between tests or one test's requests trip another's limit."""
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
    await engine.dispose()


async def upload_csv(client, text=SAMPLE_CSV) -> str:
    response = await client.post(
        "/api/data/upload",
        files={"file": ("data.csv", text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data_reference_id"]


async def upload_xlsx(client, data=None) -> str:
    response = await client.post(
        "/api/data/upload",
        files={"file": ("book.xlsx", data or xlsx_bytes(),
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data_reference_id"]


def execute_payload(nodes, edges, **extra):
    return {"nodes": nodes, "edges": edges, **extra}


# --- upload ----------------------------------------------------------------------------

async def test_upload_returns_the_reference_id_and_columns_a_source_node_needs(client):
    response = await client.post(
        "/api/data/upload", files={"file": ("data.csv", SAMPLE_CSV.encode(), "text/csv")}
    )
    body = response.json()
    assert response.status_code == 200
    assert body["data_reference_id"]
    assert body["row_count"] == 6
    assert [c["name"] for c in body["columns"]] == [
        "id", "name", "subject", "score", "grade_date", "active",
    ]


async def test_upload_of_an_xlsx_succeeds_and_is_usable_as_a_data_reference(client):
    """XLSX has no inline-text path, so the upload/cache round trip is the whole feature."""
    reference_id = await upload_xlsx(client)
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [{"id": "src", "type": "read_xlsx", "config": {"data_reference_id": reference_id}}], [],
    ))
    node_result = response.json()["node_results"]["src"]
    assert node_result["success"] is True
    assert node_result["total_row_count"] == 3


async def test_upload_rejects_an_unsupported_extension(client):
    response = await client.post("/api/data/upload", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert response.status_code == 400


async def test_sheet_can_be_selected_at_upload_time(client):
    """The one path where sheet selection actually works: the upload form's sheet_name field."""
    response = await client.post(
        "/api/data/upload",
        files={"file": ("book.xlsx", xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"sheet_name": "Sheet2"},
    )
    reference_id = response.json()["data_reference_id"]

    execute = await client.post("/api/pipeline/execute", json=execute_payload(
        [{"id": "src", "type": "read_xlsx", "config": {"data_reference_id": reference_id}}], [],
    ))
    columns = [c["name"] for c in execute.json()["node_results"]["src"]["output_schema"]["columns"]]
    assert columns == ["name", "city"]


async def test_sheet_selection_on_the_node_itself_is_honoured(client):
    """Picking a sheet in the read_xlsx config panel must change the data the node reads.

    Regression test: the upload endpoint honoured its own sheet_name form field, but the
    node's sheet_name was ignored once the data came from the data_reference_id cache — which
    is the only way the app can feed an XLSX at all. The cache now keeps the upload bytes so
    the executor can re-parse the requested sheet.
    """
    reference_id = await upload_xlsx(client)
    execute = await client.post("/api/pipeline/execute", json=execute_payload(
        [{"id": "src", "type": "read_xlsx", "config": {
            "data_reference_id": reference_id, "sheet_name": "Sheet2",
        }}], [],
    ))
    node_result = execute.json()["node_results"]["src"]
    assert node_result["success"] is True
    assert [c["name"] for c in node_result["output_schema"]["columns"]] == ["name", "city"]


async def test_switching_sheets_back_to_the_first_one_works(client):
    reference_id = await upload_xlsx(client)
    execute = await client.post("/api/pipeline/execute", json=execute_payload(
        [{"id": "src", "type": "read_xlsx", "config": {
            "data_reference_id": reference_id, "sheet_name": "Sheet1",
        }}], [],
    ))
    node_result = execute.json()["node_results"]["src"]
    assert [c["name"] for c in node_result["output_schema"]["columns"]] == ["id", "name", "amount"]


# --- catalogue ---------------------------------------------------------------------------

async def test_the_catalogue_exposes_every_node_the_canvas_can_execute(client):
    """The sidebar is built purely from this response; anything missing is unbuildable."""
    entries = (await client.get("/api/nodes")).json()
    ids = {entry["id"] for entry in entries}
    assert ids == {
        "read_csv", "read_xlsx", "filter", "sort", "select_columns", "rename_column",
        "limit_rows", "remove_duplicates", "fill_missing", "convert_type",
        "add_calculated_column", "group_by_aggregate", "pivot", "join",
        "bar_chart", "line_chart", "pie_chart", "data_table",
    }
    for entry in entries:
        assert entry["display_name"]
        assert entry["category"] in {"SOURCE", "TRANSFORM", "AGGREGATE", "JOIN", "OUTPUT"}
        assert "config_schema" in entry
        assert isinstance(entry["formula_exportable"], bool)
        assert entry["input_ports"] == (0 if entry["category"] == "SOURCE" else 2 if entry["id"] == "join" else 1)


async def test_every_catalogue_config_key_is_accepted_by_its_node(client):
    """A config key the engine ignores is a field the user can fill in that does nothing.

    One config per node type, built from the catalogue response itself so a field added to
    get_config_schema() without a matching read in execute()/infer_output_schema() shows up
    here as a node that fails on its own declared configuration.
    """
    entries = (await client.get("/api/nodes")).json()
    reference_id = await upload_csv(client, "id,name,subject,score\n1,Alice,Math,85\n2,Bob,Math,42\n")

    configs = {
        "filter": {"column": "id", "operator": "=", "value": "1"},
        "sort": {"column": "id", "direction": "ASC"},
        "select_columns": {"columns": ["id", "name"]},
        "rename_column": {"mappings": [{"from": "name", "to": "who"}]},
        "limit_rows": {"count": 1},
        "remove_duplicates": {"columns": ["id"]},
        "fill_missing": {"column": "id", "strategy": "fixed", "fixed_value": "0"},
        "convert_type": {"column": "id", "target_type": "NUMBER"},
        "add_calculated_column": {"new_column_name": "calc", "expression": "id + 1"},
        "group_by_aggregate": {
            "group_column": "subject",
            "aggregations": [{"column": "score", "function": "SUM"}],
        },
        "pivot": {
            "row_column": "subject", "column_column": "name",
            "value_column": "score", "aggregate_function": "SUM",
        },
        "bar_chart": {"x_column": "name", "y_column": "score"},
        "line_chart": {"x_column": "name", "y_column": "score"},
        "pie_chart": {"x_column": "subject", "y_column": "score"},
        "data_table": {"columns": ["name"], "rows_per_page": 10},
    }
    declared = {entry["id"] for entry in entries} - {"read_csv", "read_xlsx", "join"}
    assert declared == set(configs), "a non-source node type is missing from this test"

    for node_id, config in configs.items():
        response = await client.post("/api/pipeline/execute", json=execute_payload(
            [{"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
             {"id": "n", "type": node_id, "config": config}],
            [{"source_node_id": "src", "target_node_id": "n"}],
        ))
        assert response.status_code == 200, response.text
        node_result = response.json()["node_results"]["n"]
        assert node_result["success"] is True, (
            f"{node_id} failed with its own declared config keys: {node_result['error_message']}"
        )


# --- execute ------------------------------------------------------------------------------

async def test_a_full_source_processor_sink_pipeline_over_http(client):
    reference_id = await upload_csv(client)
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [
            {"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
            {"id": "f", "type": "filter", "config": {"column": "score", "operator": "≥", "value": "50"}},
            {"id": "g", "type": "group_by_aggregate", "config": {
                "group_column": "subject",
                "aggregations": [{"column": "score", "function": "AVERAGE"}],
            }},
            {"id": "c", "type": "bar_chart", "config": {"x_column": "subject", "y_column": "score_average"}},
        ],
        [
            {"source_node_id": "src", "target_node_id": "f"},
            {"source_node_id": "f", "target_node_id": "g"},
            {"source_node_id": "g", "target_node_id": "c"},
        ],
    ))
    assert response.status_code == 200
    node_results = response.json()["node_results"]
    assert all(r["success"] for r in node_results.values()), {
        nid: r["error_message"] for nid, r in node_results.items() if not r["success"]
    }
    assert node_results["f"]["total_row_count"] == 4
    assert node_results["c"]["preview_data"] == [
        {"subject": "Math", "score_average": 90.0},
        {"subject": "Science", "score_average": 90.0},
        {"subject": None, "score_average": 77.0},
    ]


async def test_a_join_of_two_uploads_over_http(client):
    left_id = await upload_csv(client, "id,name\n1,Alice\n2,Bob\n3,Cara\n")
    right_id = await upload_csv(client, "id,city\n1,Rome\n2,Oslo\n4,Oslo\n")
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [
            {"id": "l", "type": "read_csv", "config": {"data_reference_id": left_id}},
            {"id": "r", "type": "read_csv", "config": {"data_reference_id": right_id}},
            {"id": "j", "type": "join", "config": {"left_key": "id", "right_key": "id", "join_type": "FULL"}},
        ],
        [
            {"source_node_id": "l", "target_node_id": "j", "target_port": "left"},
            {"source_node_id": "r", "target_node_id": "j", "target_port": "right"},
        ],
    ))
    node_result = response.json()["node_results"]["j"]
    assert node_result["success"] is True
    assert node_result["total_row_count"] == 4


async def test_execution_response_is_strictly_json_serializable(client):
    """A NaN anywhere in the response makes the whole payload unparseable in the browser."""
    import json

    reference_id = await upload_csv(client, "v\n10\nabc\n30\n")
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [
            {"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
            {"id": "c", "type": "convert_type", "config": {"column": "v", "target_type": "NUMBER"}},
        ],
        [{"source_node_id": "src", "target_node_id": "c"}],
    ))
    text = response.text
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text)  # strict mode: would raise on a bare NaN token


async def test_a_failing_node_returns_200_with_a_per_node_error(client):
    """Node-level failures are data, not HTTP errors — the canvas highlights per node."""
    reference_id = await upload_csv(client)
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [
            {"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
            {"id": "f", "type": "filter", "config": {"column": "nope", "operator": "=", "value": "1"}},
        ],
        [{"source_node_id": "src", "target_node_id": "f"}],
    ))
    assert response.status_code == 200
    node_results = response.json()["node_results"]
    assert node_results["src"]["success"] is True
    assert node_results["f"]["success"] is False
    assert "nope" in node_results["f"]["error_message"]


async def test_public_routes_need_no_authorization_header(client):
    """§12's guest-mode contract, and the regression guard for it."""
    for method, url, kwargs in [
        ("get", "/api/nodes", {}),
        ("post", "/api/pipeline/execute", {"json": execute_payload([], [])}),
        ("post", "/api/pipeline/validate-edge", {"json": {
            "nodes": [], "edges": [],
            "proposed_edge": {"source_node_id": "a", "target_node_id": "b"},
        }}),
    ]:
        response = await getattr(client, method)(url, **kwargs)
        assert response.status_code == 200, f"{url} required auth: {response.status_code}"


async def test_partial_execution_over_http_returns_only_the_upstream_nodes(client):
    reference_id = await upload_csv(client)
    response = await client.post("/api/pipeline/execute", json=execute_payload(
        [
            {"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
            {"id": "f", "type": "filter", "config": {"column": "score", "operator": ">", "value": "50"}},
            {"id": "d", "type": "data_table", "config": {}},
        ],
        [
            {"source_node_id": "src", "target_node_id": "f"},
            {"source_node_id": "f", "target_node_id": "d"},
        ],
        target_node_id="f",
    ))
    assert set(response.json()["node_results"]) == {"src", "f"}


# --- edge validation -------------------------------------------------------------------------

async def _validate(client, nodes, edges, proposed):
    return await client.post("/api/pipeline/validate-edge", json={
        "nodes": nodes, "edges": edges, "proposed_edge": proposed,
    })


async def test_edge_validation_accepts_a_legal_connection(client):
    response = await _validate(
        client,
        [{"id": "a", "type": "read_csv", "config": {}}, {"id": "b", "type": "filter", "config": {}}],
        [],
        {"source_node_id": "a", "target_node_id": "b"},
    )
    assert response.json() == {"valid": True, "error_message": None}


@pytest.mark.parametrize(
    "nodes,edges,proposed,expected_fragment",
    [
        ([{"id": "a", "type": "read_csv", "config": {}}], [],
         {"source_node_id": "a", "target_node_id": "a"}, "itself"),
        ([{"id": "a", "type": "read_csv", "config": {}}, {"id": "b", "type": "read_csv", "config": {}}], [],
         {"source_node_id": "a", "target_node_id": "b"}, "does not accept an input"),
        ([{"id": "a", "type": "read_csv", "config": {}}, {"id": "b", "type": "filter", "config": {}},
          {"id": "c", "type": "filter", "config": {}}],
         [{"source_node_id": "a", "target_node_id": "b"},
          {"source_node_id": "a", "target_node_id": "c"}],
         {"source_node_id": "a", "target_node_id": "b"}, "already has a connected input"),
    ],
)
async def test_edge_validation_rejects_illegal_connections(client, nodes, edges, proposed, expected_fragment):
    body = (await _validate(client, nodes, edges, proposed)).json()
    assert body["valid"] is False
    assert expected_fragment in body["error_message"]


async def test_edge_validation_rejects_a_connection_that_would_create_a_cycle(client):
    # A back edge into a single-input node always trips the "already connected" capacity
    # check first, so the only way to reach the cycle check is through a join's free port:
    # l -> j(left) -> x, proposing x -> j(right) closes the loop.
    body = (await _validate(
        client,
        [{"id": "l", "type": "read_csv", "config": {}},
         {"id": "j", "type": "join", "config": {}},
         {"id": "x", "type": "filter", "config": {}}],
        [{"source_node_id": "l", "target_node_id": "j", "target_port": "left"},
         {"source_node_id": "j", "target_node_id": "x"}],
        {"source_node_id": "x", "target_node_id": "j", "target_port": "right"},
    )).json()
    assert body["valid"] is False
    assert "cycle" in body["error_message"].lower()


async def test_join_ports_must_be_specified_and_cannot_be_double_connected(client):
    join_nodes = [{"id": "l", "type": "read_csv", "config": {}},
                  {"id": "r", "type": "read_csv", "config": {}},
                  {"id": "j", "type": "join", "config": {}}]
    no_port = (await _validate(client, join_nodes, [], {"source_node_id": "l", "target_node_id": "j"})).json()
    assert no_port["valid"] is False

    taken = (await _validate(
        client, join_nodes,
        [{"source_node_id": "l", "target_node_id": "j", "target_port": "left"}],
        {"source_node_id": "r", "target_node_id": "j", "target_port": "left"},
    )).json()
    assert taken["valid"] is False
    assert "already connected" in taken["error_message"]


# --- export -------------------------------------------------------------------------------------

async def test_export_returns_a_csv_attachment_of_the_target_node(client):
    reference_id = await upload_csv(client, "n\n" + "".join(f"{i}\n" for i in range(150)))
    response = await client.post("/api/pipeline/export", json=execute_payload(
        [{"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}}],
        [], target_node_id="src",
    ))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert len(response.text.strip().splitlines()) == 151  # header + 150 rows, not the 100-row preview


async def test_export_of_a_failing_node_is_a_400_with_a_reason(client):
    reference_id = await upload_csv(client)
    response = await client.post("/api/pipeline/export", json=execute_payload(
        [
            {"id": "src", "type": "read_csv", "config": {"data_reference_id": reference_id}},
            {"id": "f", "type": "filter", "config": {"column": "nope", "operator": "=", "value": "1"}},
        ],
        [{"source_node_id": "src", "target_node_id": "f"}],
        target_node_id="f",
    ))
    assert response.status_code == 400
    assert "nope" in response.json()["detail"]
