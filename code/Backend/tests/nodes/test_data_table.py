import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import NodeCategory, SchemaValidationError
from app.nodes.output.data_table import DataTableNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
        Column(name="city", type=DataType.STRING),
    ])
    df = pd.DataFrame({"name": ["Alice"], "age": [30], "city": ["NYC"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=1)


def test_category_and_ports():
    node = DataTableNode()
    assert node.category == NodeCategory.OUTPUT
    assert node.input_ports == 1


def test_infer_output_schema_no_columns_is_identity():
    node = DataTableNode()
    fdf = _fdf()
    result = node.infer_output_schema(fdf.schema, {})
    assert result is fdf.schema


def test_infer_output_schema_restricts_columns():
    node = DataTableNode()
    result = node.infer_output_schema(_fdf().schema, {"columns": ["city", "name"]})
    assert result.column_names() == ["city", "name"]


def test_infer_output_schema_missing_column_raises():
    node = DataTableNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"columns": ["missing"]})


def test_execute_no_columns_is_passthrough():
    node = DataTableNode()
    fdf = _fdf()
    result = node.execute(fdf, {})
    assert result is fdf


def test_execute_restricts_columns():
    node = DataTableNode()
    result = node.execute(_fdf(), {"columns": ["city", "name"]})
    assert list(result.df.columns) == ["city", "name"]
    assert result.schema.column_names() == ["city", "name"]


def test_to_excel_formula_is_identity():
    node = DataTableNode()
    assert node.to_excel_formula("FILTER(RANGE, cond)", {}) == "FILTER(RANGE, cond)"


def test_to_excel_formula_none_input_ref():
    node = DataTableNode()
    assert node.to_excel_formula(None, {}) is None
