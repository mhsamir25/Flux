import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.select_columns import SelectColumnsNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
        Column(name="city", type=DataType.STRING),
    ])
    df = pd.DataFrame({"name": ["Alice"], "age": [30], "city": ["NYC"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=1)


def test_infer_output_schema_no_columns_raises():
    node = SelectColumnsNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"columns": []})


def test_infer_output_schema_missing_column_raises():
    node = SelectColumnsNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"columns": ["missing"]})


def test_infer_output_schema_preserves_order():
    node = SelectColumnsNode()
    result = node.infer_output_schema(_fdf().schema, {"columns": ["city", "name"]})
    assert result.column_names() == ["city", "name"]


def test_execute_restricts_and_reorders_columns():
    node = SelectColumnsNode()
    result = node.execute(_fdf(), {"columns": ["city", "name"]})
    assert list(result.df.columns) == ["city", "name"]
    assert result.schema.column_names() == ["city", "name"]


def test_to_excel_formula():
    node = SelectColumnsNode()
    formula = node.to_excel_formula("RANGE", {"columns": ["name", "age"]})
    assert formula == "CHOOSECOLS(RANGE, [name], [age])"


def test_to_excel_formula_none_without_columns():
    node = SelectColumnsNode()
    assert node.to_excel_formula("RANGE", {}) is None
