import uuid

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import schemas
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.dependencies import current_active_user, current_user_optional
from app.auth.manager import UserManager
from app.auth.models import User
from app.db import Base, get_session


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _make_manager(maker) -> UserManager:
    session = maker()
    user_db = SQLAlchemyUserDatabase(session, User)
    return UserManager(user_db)


# --- User model shape -----------------------------------------------------------------

def test_user_table_has_expected_columns():
    columns = {c.name for c in User.__table__.columns}
    assert columns == {"id", "email", "hashed_password", "is_active", "is_superuser", "is_verified"}


def test_user_id_is_uuid_primary_key():
    id_column = User.__table__.columns["id"]
    assert id_column.primary_key


# --- UserManager: create / password hashing --------------------------------------------

@pytest.mark.asyncio
async def test_create_user_hashes_password_not_plaintext(session_maker):
    manager = await _make_manager(session_maker)
    user = await manager.create(schemas.BaseUserCreate(email="alice@example.com", password="s3cret!"))
    assert user.email == "alice@example.com"
    assert user.hashed_password != "s3cret!"
    assert len(user.hashed_password) > 20  # a real hash, not a truncated/no-op value
    assert user.is_active is True
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises(session_maker):
    manager = await _make_manager(session_maker)
    await manager.create(schemas.BaseUserCreate(email="dup@example.com", password="pw123456"))
    manager2 = await _make_manager(session_maker)
    with pytest.raises(Exception):
        await manager2.create(schemas.BaseUserCreate(email="dup@example.com", password="pw123456"))


# --- UserManager: authenticate ----------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_correct_credentials_returns_user(session_maker):
    manager = await _make_manager(session_maker)
    await manager.create(schemas.BaseUserCreate(email="bob@example.com", password="correct-horse"))

    manager2 = await _make_manager(session_maker)
    result = await manager2.authenticate(
        OAuth2PasswordRequestForm(username="bob@example.com", password="correct-horse")
    )
    assert result is not None
    assert result.email == "bob@example.com"


@pytest.mark.asyncio
async def test_authenticate_wrong_password_returns_none(session_maker):
    manager = await _make_manager(session_maker)
    await manager.create(schemas.BaseUserCreate(email="carol@example.com", password="right-password"))

    manager2 = await _make_manager(session_maker)
    result = await manager2.authenticate(
        OAuth2PasswordRequestForm(username="carol@example.com", password="wrong-password")
    )
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_unknown_email_returns_none(session_maker):
    manager = await _make_manager(session_maker)
    result = await manager.authenticate(
        OAuth2PasswordRequestForm(username="nobody@example.com", password="whatever")
    )
    assert result is None


# --- JWT strategy: write/read round-trip ------------------------------------------------

@pytest.mark.asyncio
async def test_jwt_token_round_trips_to_correct_user(session_maker):
    manager = await _make_manager(session_maker)
    user = await manager.create(schemas.BaseUserCreate(email="dave@example.com", password="pw123456"))

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    assert isinstance(token, str) and token

    manager2 = await _make_manager(session_maker)
    decoded_user = await strategy.read_token(token, manager2)
    assert decoded_user is not None
    assert decoded_user.email == "dave@example.com"


@pytest.mark.asyncio
async def test_jwt_garbage_token_fails_to_decode(session_maker):
    manager = await _make_manager(session_maker)
    strategy = get_jwt_strategy()
    result = await strategy.read_token("not-a-real-jwt", manager)
    assert result is None


def test_auth_backend_configured_as_jwt():
    assert auth_backend.name == "jwt"


# --- current_user_optional / current_active_user, wired into a minimal test app -----------

@pytest_asyncio.fixture
async def test_app(session_maker):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user=Depends(current_user_optional)):
        return {"email": user.email if user else None}

    @app.get("/protected")
    async def protected(user=Depends(current_active_user)):
        return {"email": user.email}

    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_current_user_optional_returns_none_without_token(client):
    response = await client.get("/whoami")
    assert response.status_code == 200
    assert response.json() == {"email": None}


@pytest.mark.asyncio
async def test_current_user_optional_returns_user_with_valid_token(client, session_maker):
    manager = await _make_manager(session_maker)
    user = await manager.create(schemas.BaseUserCreate(email="erin@example.com", password="pw123456"))
    token = await get_jwt_strategy().write_token(user)

    response = await client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"email": "erin@example.com"}


@pytest.mark.asyncio
async def test_current_user_optional_returns_none_for_invalid_token(client):
    response = await client.get("/whoami", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 200
    assert response.json() == {"email": None}


@pytest.mark.asyncio
async def test_current_active_user_rejects_missing_token(client):
    response = await client.get("/protected")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_current_active_user_accepts_valid_token(client, session_maker):
    manager = await _make_manager(session_maker)
    user = await manager.create(schemas.BaseUserCreate(email="frank@example.com", password="pw123456"))
    token = await get_jwt_strategy().write_token(user)

    response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"email": "frank@example.com"}


@pytest.mark.asyncio
async def test_current_active_user_rejects_inactive_user(client, session_maker):
    manager = await _make_manager(session_maker)
    user = await manager.create(schemas.BaseUserCreate(email="grace@example.com", password="pw123456"))
    await manager.update(schemas.BaseUserUpdate(is_active=False), user)
    token = await get_jwt_strategy().write_token(user)

    response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
