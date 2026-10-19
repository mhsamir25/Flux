import pytest

from app.engine.registry import NodeRegistry, build_registry
from app.nodes.base import FieldSchema, NodeCategory, NodePlugin


class DummySourceNode(NodePlugin):
    id = "dummy_source"
    display_name = "Dummy Source"
    category = NodeCategory.SOURCE
    input_ports = 0

    def get_config_schema(self) -> list[FieldSchema]:
        return []

    def infer_output_schema(self, input_schema, config):
        return input_schema

    def execute(self, input_df, config):
        raise NotImplementedError

    def execute_source(self, config):
        return "executed"


class DummyTransformNode(NodePlugin):
    id = "dummy_transform"
    display_name = "Dummy Transform"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return []

    def infer_output_schema(self, input_schema, config):
        return input_schema

    def execute(self, input_df, config):
        return input_df


def test_register_and_get():
    registry = NodeRegistry()
    node = DummySourceNode()
    registry.register(node)
    assert registry.get("dummy_source") is node


def test_get_missing_id_raises_keyerror():
    registry = NodeRegistry()
    with pytest.raises(KeyError):
        registry.get("does_not_exist")


def test_all_returns_every_registered_plugin():
    registry = NodeRegistry()
    source = DummySourceNode()
    transform = DummyTransformNode()
    registry.register(source)
    registry.register(transform)
    assert set(registry.all()) == {source, transform}


def test_all_empty_registry():
    registry = NodeRegistry()
    assert registry.all() == []


def test_register_same_id_overwrites():
    registry = NodeRegistry()
    first = DummyTransformNode()
    second = DummyTransformNode()
    registry.register(first)
    registry.register(second)
    assert registry.get("dummy_transform") is second
    assert len(registry.all()) == 1


def test_build_registry_returns_registry_instance():
    registry = build_registry()
    assert isinstance(registry, NodeRegistry)


def test_build_registry_includes_source_nodes():
    registry = build_registry()
    ids = {plugin.id for plugin in registry.all()}
    assert {"read_csv", "read_xlsx"} <= ids
    assert registry.get("read_csv").__class__.__name__ == "ReadCsvNode"
    assert registry.get("read_xlsx").__class__.__name__ == "ReadXlsxNode"


def test_build_registry_includes_transform_nodes():
    registry = build_registry()
    ids = {plugin.id for plugin in registry.all()}
    expected = {
        "filter", "sort", "select_columns", "rename_column", "limit_rows",
        "remove_duplicates", "fill_missing", "convert_type", "add_calculated_column",
    }
    assert expected <= ids


def test_build_registry_includes_aggregate_and_join_nodes():
    registry = build_registry()
    ids = {plugin.id for plugin in registry.all()}
    assert {"group_by_aggregate", "pivot", "join"} <= ids


def test_build_registry_includes_output_nodes():
    registry = build_registry()
    ids = {plugin.id for plugin in registry.all()}
    assert {"bar_chart", "line_chart", "pie_chart", "data_table"} <= ids


def test_build_registry_has_every_node_plugin_from_the_plan():
    # PLAN.md §5 says "17 NodePlugin classes" / "Implement all 17," but its own §6 bullet
    # list enumerates 18 distinct node ids (2 source + 9 transform + 2 aggregate + 1 join +
    # 4 output) — a miscount in the plan itself, not something to silently "round down" here.
    # This asserts against every id actually specified in §6.
    registry = build_registry()
    ids = {plugin.id for plugin in registry.all()}
    every_node_in_the_plan = {
        "read_csv", "read_xlsx",
        "filter", "sort", "select_columns", "rename_column", "limit_rows",
        "remove_duplicates", "fill_missing", "convert_type", "add_calculated_column",
        "group_by_aggregate", "pivot",
        "join",
        "bar_chart", "line_chart", "pie_chart", "data_table",
    }
    assert len(every_node_in_the_plan) == 18
    assert ids == every_node_in_the_plan
