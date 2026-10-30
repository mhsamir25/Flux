import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.rename_column import RenameColumnNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({"name": ["Alice"], "age": [30]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=1)


def test_infer_output_schema_renames():
    node = RenameColumnNode()
    result = node.infer_output_schema(_fdf().schema, {"mappings": [{"from": "name", "to": "full_name"}]})
    assert result.column_names() == ["full_name", "age"]
    assert result.get_column("full_name").type == DataType.STRING


def test_infer_output_schema_missing_source_column_raises():
    node = RenameColumnNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"mappings": [{"from": "missing", "to": "x"}]})


def test_infer_output_schema_duplicate_target_raises():
    node = RenameColumnNode()
    config = {"mappings": [{"from": "name", "to": "age"}]}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_execute_renames_columns():
    node = RenameColumnNode()
    result = node.execute(_fdf(), {"mappings": [{"from": "name", "to": "full_name"}]})
    assert list(result.df.columns) == ["full_name", "age"]
    assert result.schema.column_names() == ["full_name", "age"]


def test_execute_no_mappings_is_noop():
    node = RenameColumnNode()
    result = node.execute(_fdf(), {"mappings": []})
    assert list(result.df.columns) == ["name", "age"]


def test_to_excel_formula_is_none():
    node = RenameColumnNode()
    assert node.to_excel_formula("RANGE", {"mappings": []}) is None


def test_to_excel_formula_explanation_mentions_no_equivalent():
    node = RenameColumnNode()
    explanation = node.to_excel_formula_explanation({"mappings": [{"from": "name", "to": "full_name"}]})
    assert "No Excel formula equivalent" in explanation
