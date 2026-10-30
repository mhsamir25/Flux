import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

_MIGRATION_PATH = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "59c0a5b719e2_initial_schema.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("initial_schema_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration():
    return _load_migration()


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    yield eng
    eng.dispose()


def test_upgrade_creates_all_three_tables(migration, engine):
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        table_names = set(inspect(connection).get_table_names())
        assert {"user", "pipeline_template", "execution_log"} <= table_names


def test_upgrade_creates_correct_columns(migration, engine):
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        inspector = inspect(connection)
        user_columns = {c["name"] for c in inspector.get_columns("user")}
        template_columns = {c["name"] for c in inspector.get_columns("pipeline_template")}
        log_columns = {c["name"] for c in inspector.get_columns("execution_log")}

        assert user_columns == {"id", "email", "hashed_password", "is_active", "is_superuser", "is_verified"}
        assert template_columns == {
            "id", "owner_id", "name", "description", "pipeline_json", "created_at", "updated_at",
        }
        assert log_columns == {"id", "template_id", "status", "error_summary", "run_at"}


def test_upgrade_creates_unique_email_index(migration, engine):
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        indexes = inspect(connection).get_indexes("user")
        email_index = next(ix for ix in indexes if ix["name"] == "ix_user_email")
        assert bool(email_index["unique"])
        assert email_index["column_names"] == ["email"]


def test_upgrade_then_insert_rows_via_raw_sql(migration, engine):
    """Confirms the created schema actually accepts real data, not just that DDL ran without
    error — inserts a user, a template owned by it, and an execution log referencing it."""
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        connection.execute(text(
            "INSERT INTO \"user\" (id, email, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES ('11111111-1111-1111-1111-111111111111', 'a@example.com', 'hash', 1, 0, 0)"
        ))
        connection.execute(text(
            "INSERT INTO pipeline_template (id, owner_id, name, pipeline_json, created_at, updated_at) "
            "VALUES ('22222222-2222-2222-2222-222222222222', "
            "'11111111-1111-1111-1111-111111111111', 'My Pipeline', '{}', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            "INSERT INTO execution_log (id, template_id, status, run_at) "
            "VALUES ('33333333-3333-3333-3333-333333333333', "
            "'22222222-2222-2222-2222-222222222222', 'success', CURRENT_TIMESTAMP)"
        ))
        connection.commit()

        row_count = connection.execute(text("SELECT COUNT(*) FROM execution_log")).scalar()
        assert row_count == 1


def test_status_check_constraint_rejects_invalid_value(migration, engine):
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        with pytest.raises(Exception):
            connection.execute(text(
                "INSERT INTO execution_log (id, template_id, status, run_at) "
                "VALUES ('44444444-4444-4444-4444-444444444444', NULL, 'bogus', CURRENT_TIMESTAMP)"
            ))
            connection.commit()


def test_downgrade_removes_all_tables(migration, engine):
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        connection.commit()

        with Operations.context(ctx):
            migration.downgrade()
        connection.commit()

        table_names = set(inspect(connection).get_table_names())
        assert table_names == set()
