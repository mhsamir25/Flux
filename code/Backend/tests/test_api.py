import io

import openpyxl
import pytest
import pytest_asyncio
from fastapi_users import schemas
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.backend import get_jwt_strategy
from app.auth.manager import UserManager
from app.auth.models import User
from app.db import Base, get_session
from app.main import app
from app.models.execution_log import ExecutionLog
from app.models.pipeline_template import PipelineTemplate  # noqa: F401 (registers the table)
from app.rate_limit import limiter


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_maker):
    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _create_user_and_token(session_maker, email="user@example.com", password="pw123456"):
    async with session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        user = await manager.create(schemas.BaseUserCreate(email=email, password=password))
        token = await get_jwt_strategy().write_token(user)
        return user, token


def _linear_pipeline_request(**overrides):
    body = {
        "nodes": [
            {"id": "n1", "type": "read_csv", "config": {}},
            {"id": "n2", "type": "filter", "config": {"column": "age", "operator": ">", "value": "25"}},
        ],
        "edges": [{"source_node_id": "n1", "target_node_id": "n2"}],
        "csv_data": "name,age\nAlice,30\nBob,20",
    }
    body.update(overrides)
    return body


# --- guest-mode regression: every public route works with zero Authorization header --------

@pytest.mark.asyncio
async def test_get_nodes_works_without_auth(client):
    response = await client.get("/api/nodes")
    assert response.status_code == 200
    assert len(response.json()) == 18


@pytest.mark.asyncio
async def test_pipeline_execute_works_without_auth(client):
    response = await client.post("/api/pipeline/execute", json=_linear_pipeline_request())
    assert response.status_code == 200
    body = response.json()
    assert body["node_results"]["n2"]["success"] is True


@pytest.mark.asyncio
async def test_pipeline_export_works_without_auth(client):
    body = _linear_pipeline_request(target_node_id="n2")
    response = await client.post("/api/pipeline/export", json=body)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="n2.csv"' in response.headers["content-disposition"]
    assert response.text.strip().splitlines() == ["name,age", "Alice,30"]


@pytest.mark.asyncio
async def test_pipeline_export_missing_target_node_id_is_400(client):
    body = _linear_pipeline_request()
    body.pop("target_node_id", None)
    response = await client.post("/api/pipeline/export", json=body)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_pipeline_export_failed_node_is_400(client):
    body = _linear_pipeline_request(target_node_id="n2")
    body["nodes"][1]["config"] = {"column": "missing_col", "operator": ">", "value": "1"}
    response = await client.post("/api/pipeline/export", json=body)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_validate_edge_works_without_auth(client):
    body = {
        "nodes": [
            {"id": "n1", "type": "read_csv", "config": {}},
            {"id": "n2", "type": "filter", "config": {}},
        ],
        "edges": [],
        "proposed_edge": {"source_node_id": "n1", "target_node_id": "n2"},
    }
    response = await client.post("/api/pipeline/validate-edge", json=body)
    assert response.status_code == 200
    assert response.json() == {"valid": True, "error_message": None}


@pytest.mark.asyncio
async def test_formula_generate_works_without_auth(client):
    body = {
        "nodes": [
            {"id": "n1", "type": "read_csv", "config": {}},
            {"id": "n2", "type": "sort", "config": {"column": "age", "direction": "DESC"}},
        ],
        "edges": [{"source_node_id": "n1", "target_node_id": "n2"}],
    }
    response = await client.post("/api/formula/generate", json=body)
    assert response.status_code == 200
    assert response.json()["formula"] == "=SORT(Sheet1!A1:Z1000, [age], -1)"


@pytest.mark.asyncio
async def test_formula_parse_works_without_auth(client):
    response = await client.post("/api/formula/parse", json={"formula": "=UNIQUE(Sheet1!A1:Z1000)"})
    assert response.status_code == 200
    assert "nodes" in response.json()


@pytest.mark.asyncio
async def test_data_upload_works_without_auth(client):
    files = {"file": ("data.csv", b"a,b\n1,2\n3,4", "text/csv")}
    response = await client.post("/api/data/upload", files=files)
    assert response.status_code == 200
    assert response.json()["row_count"] == 2


@pytest.mark.asyncio
async def test_data_upload_xlsx_works_without_auth(client):
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    wb.active.append([1, 2])
    buffer = io.BytesIO()
    wb.save(buffer)
    files = {"file": ("data.xlsx", buffer.getvalue(), "application/vnd.openxmlformats")}
    response = await client.post("/api/data/upload", files=files)
    assert response.status_code == 200
    assert response.json()["row_count"] == 1


@pytest.mark.asyncio
async def test_data_upload_rejects_bad_extension(client):
    files = {"file": ("data.exe", b"not data", "application/octet-stream")}
    response = await client.post("/api/data/upload", files=files)
    assert response.status_code == 400


# --- auth-required routes correctly reject missing/invalid auth ---------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/templates"),
    ("POST", "/api/templates"),
    ("GET", "/api/templates/00000000-0000-0000-0000-000000000000"),
    ("PUT", "/api/templates/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/templates/00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/users/me"),
])
async def test_templates_and_me_reject_missing_auth(client, method, path):
    response = await client.request(method, path, json={} if method in ("POST", "PUT") else None)
    assert response.status_code == 401


# --- auth flow: register -> login -> current user ------------------------------------------

@pytest.mark.asyncio
async def test_register_then_login_then_get_current_user(client):
    register_body = {"email": "newuser@example.com", "password": "pw123456"}
    r1 = await client.post("/api/auth/register", json=register_body)
    assert r1.status_code == 201
    assert r1.json()["email"] == "newuser@example.com"

    r2 = await client.post(
        "/api/auth/jwt/login",
        data={"username": "newuser@example.com", "password": "pw123456"},
    )
    assert r2.status_code == 200
    token = r2.json()["access_token"]

    r3 = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    assert r3.json()["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    await client.post("/api/auth/register", json={"email": "wp@example.com", "password": "right-pass"})
    response = await client.post(
        "/api/auth/jwt/login", data={"username": "wp@example.com", "password": "wrong-pass"}
    )
    assert response.status_code == 400


# --- template ownership enforcement ---------------------------------------------------------

@pytest.mark.asyncio
async def test_template_crud_lifecycle(client, session_maker):
    _, token = await _create_user_and_token(session_maker, email="owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_body = {"name": "Pipeline A", "description": None, "pipeline_json": {"nodes": [], "edges": []}}
    r1 = await client.post("/api/templates", json=create_body, headers=headers)
    assert r1.status_code == 201
    template_id = r1.json()["id"]

    r2 = await client.get("/api/templates", headers=headers)
    assert len(r2.json()) == 1

    r3 = await client.put(f"/api/templates/{template_id}", json={"name": "Renamed"}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["name"] == "Renamed"

    r4 = await client.delete(f"/api/templates/{template_id}", headers=headers)
    assert r4.status_code == 204

    r5 = await client.get(f"/api/templates/{template_id}", headers=headers)
    assert r5.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_template(client, session_maker):
    _, alice_token = await _create_user_and_token(session_maker, email="alice2@example.com")
    _, bob_token = await _create_user_and_token(session_maker, email="bob2@example.com")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    create_body = {"name": "Alice's Pipeline", "pipeline_json": {"nodes": [], "edges": []}}
    r1 = await client.post("/api/templates", json=create_body, headers=alice_headers)
    template_id = r1.json()["id"]

    r2 = await client.get(f"/api/templates/{template_id}", headers=bob_headers)
    assert r2.status_code == 404

    r3 = await client.put(f"/api/templates/{template_id}", json={"name": "Hijacked"}, headers=bob_headers)
    assert r3.status_code == 404

    r4 = await client.delete(f"/api/templates/{template_id}", headers=bob_headers)
    assert r4.status_code == 404

    r5 = await client.get("/api/templates", headers=bob_headers)
    assert r5.json() == []


# --- execution logging ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_writes_execution_log_row(client, session_maker):
    response = await client.post("/api/pipeline/execute", json=_linear_pipeline_request())
    assert response.status_code == 200

    async with session_maker() as session:
        rows = (await session.execute(select(ExecutionLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "success"
        assert rows[0].template_id is None


@pytest.mark.asyncio
async def test_execute_with_failure_logs_error_status(client, session_maker):
    body = _linear_pipeline_request()
    body["nodes"][1]["config"] = {"column": "missing_col", "operator": ">", "value": "1"}
    response = await client.post("/api/pipeline/execute", json=body)
    assert response.status_code == 200

    async with session_maker() as session:
        rows = (await session.execute(select(ExecutionLog))).scalars().all()
        assert rows[0].status == "error"
        assert rows[0].error_summary


# --- rate limiting ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_execute_guest_rate_limit_trips_after_thirty(client):
    statuses = []
    for _ in range(32):
        response = await client.post("/api/pipeline/execute", json=_linear_pipeline_request())
        statuses.append(response.status_code)
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


@pytest.mark.asyncio
async def test_pipeline_execute_authenticated_gets_higher_limit(client, session_maker):
    _, token = await _create_user_and_token(session_maker, email="heavy@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    statuses = []
    for _ in range(35):
        response = await client.post("/api/pipeline/execute", json=_linear_pipeline_request(), headers=headers)
        statuses.append(response.status_code)
    assert statuses.count(200) == 35  # past the 30/minute guest ceiling, still all succeed


@pytest.mark.asyncio
async def test_data_upload_guest_rate_limit_trips_after_thirty(client):
    files = {"file": ("data.csv", b"a\n1", "text/csv")}
    statuses = []
    for _ in range(32):
        response = await client.post("/api/data/upload", files=files)
        statuses.append(response.status_code)
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429
