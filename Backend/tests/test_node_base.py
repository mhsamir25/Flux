import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import (
    FieldSchema,
    FieldType,
    NodeCategory,
    NodePlugin,
    SchemaValidationError,
)


class DummyTransformNode(NodePlugin):
    id = "dummy_transform"
    display_name = "Dummy Transform"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self):
        return [FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT)]

    def infer_output_schema(self, input_schema, config):
        if not input_schema.has_column(config.get("column", "")):
            raise SchemaValidationError(f"Column '{config.get('column')}' not found")
        return input_schema

    def execute(self, input_df, config):
        return input_df


def test_node_category_values():
    assert NodeCategory.SOURCE == "SOURCE"
    assert NodeCategory.TRANSFORM == "TRANSFORM"
    assert NodeCategory.AGGREGATE == "AGGREGATE"
    assert NodeCategory.JOIN == "JOIN"
    assert NodeCategory.OUTPUT == "OUTPUT"


def test_field_type_values():
    assert FieldType.COLUMN_SELECT == "COLUMN_SELECT"
    assert FieldType.EXPRESSION == "EXPRESSION"


def test_field_schema_defaults():
    field = FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT)
    assert field.required is True
    assert field.placeholder is None
    assert field.options is None


def test_field_schema_with_options():
    field = FieldSchema(
        key="operator", label="Operator", type=FieldType.ENUM,
        options=["=", "!=", ">"], required=False,
    )
    assert field.options == ["=", "!=", ">"]
    assert field.required is False


def test_cannot_instantiate_nodeplugin_directly():
    with pytest.raises(TypeError):
        NodePlugin()


def test_subclass_missing_abstract_method_cannot_instantiate():
    class Incomplete(NodePlugin):
        id = "incomplete"
        display_name = "Incomplete"
        category = NodeCategory.TRANSFORM

        def get_config_schema(self):
            return []

        def infer_output_schema(self, input_schema, config):
            return input_schema
        # execute() intentionally not implemented

    with pytest.raises(TypeError):
        Incomplete()


def test_default_ports():
    node = DummyTransformNode()
    assert node.input_ports == 1
    assert node.output_ports == 1


def test_execute_join_default_raises_not_implemented():
    node = DummyTransformNode()
    with pytest.raises(NotImplementedError):
        node.execute_join(None, None, {})


def test_execute_source_default_raises_not_implemented():
    node = DummyTransformNode()
    with pytest.raises(NotImplementedError):
        node.execute_source({})


def test_to_excel_formula_defaults_to_none():
    node = DummyTransformNode()
    assert node.to_excel_formula("A1:A10", {}) is None


def test_to_excel_formula_explanation_defaults_to_empty_string():
    node = DummyTransformNode()
    assert node.to_excel_formula_explanation({}) == ""


def test_infer_output_schema_raises_schema_validation_error():
    node = DummyTransformNode()
    schema = DataSchema(columns=[Column(name="age", type=DataType.NUMBER)])
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(schema, {"column": "missing"})


def test_infer_output_schema_success():
    node = DummyTransformNode()
    schema = DataSchema(columns=[Column(name="age", type=DataType.NUMBER)])
    result = node.infer_output_schema(schema, {"column": "age"})
    assert result is schema


def test_execute_passthrough():
    node = DummyTransformNode()
    schema = DataSchema(columns=[Column(name="age", type=DataType.NUMBER)])
    fdf = FluxDataFrame(schema=schema, df=pd.DataFrame({"age": [1, 2]}), total_row_count=2)
    result = node.execute(fdf, {"column": "age"})
    assert result is fdf
