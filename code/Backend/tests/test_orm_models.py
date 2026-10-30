import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import User
from app.db import Base
from app.models.execution_log import ExecutionLog
from app.models.pipeline_template import PipelineTemplate


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _make_user(session_maker, email="owner@example.com") -> User:
    async with session_maker() as session:
        user = User(
            id=uuid.uuid4(), email=email, hashed_password="hashed",
            is_active=True, is_superuser=False, is_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# --- table shape ----------------------------------------------------------------

def test_pipeline_template_columns():
    columns = {c.name for c in PipelineTemplate.__table__.columns}
    assert columns == {"id", "owner_id", "name", "description", "pipeline_json", "created_at", "updated_at"}


def test_pipeline_template_owner_id_foreign_key():
    fks = list(PipelineTemplate.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "user.id"


def test_execution_log_columns():
    columns = {c.name for c in ExecutionLog.__table__.columns}
    assert columns == {"id", "template_id", "status", "error_summary", "run_at"}


def test_execution_log_template_id_nullable_and_fk():
    template_id_col = ExecutionLog.__table__.columns["template_id"]
    assert template_id_col.nullable is True
    fks = list(ExecutionLog.__table__.foreign_keys)
    assert fks[0].target_fullname == "pipeline_template.id"


# --- CRUD round-trip -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_pipeline_template_owned_by_user(session_maker):
    owner = await _make_user(session_maker)
    pipeline_json = {"version": "1.0", "nodes": [{"id": "n1", "type": "read_csv", "config": {}}], "edges": []}

    async with session_maker() as session:
        template = PipelineTemplate(
            id=uuid.uuid4(), owner_id=owner.id, name="My Pipeline",
            description="A test pipeline", pipeline_json=pipeline_json,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)

        assert template.name == "My Pipeline"
        assert template.pipeline_json == pipeline_json
        assert template.created_at is not None
        assert template.updated_at is not None


@pytest.mark.asyncio
async def test_pipeline_template_requires_owner(session_maker):
    async with session_maker() as session:
        template = PipelineTemplate(
            id=uuid.uuid4(), owner_id=None, name="Orphan", pipeline_json={"nodes": [], "edges": []},
        )
        session.add(template)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_execution_log_for_saved_template(session_maker):
    owner = await _make_user(session_maker)
    async with session_maker() as session:
        template = PipelineTemplate(
            id=uuid.uuid4(), owner_id=owner.id, name="P", pipeline_json={"nodes": [], "edges": []},
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)

        log = ExecutionLog(id=uuid.uuid4(), template_id=template.id, status="success")
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.status == "success"
        assert log.template_id == template.id
        assert log.run_at is not None


@pytest.mark.asyncio
async def test_execution_log_guest_run_has_null_template_id(session_maker):
    async with session_maker() as session:
        log = ExecutionLog(id=uuid.uuid4(), template_id=None, status="error", error_summary="Column not found")
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.template_id is None
        assert log.error_summary == "Column not found"


@pytest.mark.asyncio
async def test_execution_log_status_check_constraint_rejects_invalid_value(session_maker):
    async with session_maker() as session:
        log = ExecutionLog(id=uuid.uuid4(), template_id=None, status="not_a_real_status")
        session.add(log)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_pipeline_template_updated_at_changes_on_update(session_maker):
    owner = await _make_user(session_maker)
    async with session_maker() as session:
        template = PipelineTemplate(
            id=uuid.uuid4(), owner_id=owner.id, name="Original", pipeline_json={"nodes": [], "edges": []},
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        first_updated_at = template.updated_at

        template.name = "Renamed"
        await session.commit()
        await session.refresh(template)

        assert template.name == "Renamed"
        assert template.updated_at >= first_updated_at
