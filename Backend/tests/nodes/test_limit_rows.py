import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.limit_rows import LimitRowsNode


def _fdf():
    schema = DataSchema(columns=[Column(name="id", type=DataType.NUMBER)])
    df = pd.DataFrame({"id": [1, 2, 3, 4, 5]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=5)


def test_infer_output_schema_negative_count_raises():
    node = LimitRowsNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"count": -1})


def test_infer_output_schema_missing_count_raises():
    node = LimitRowsNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {})


def test_infer_output_schema_invalid_count_raises():
    node = LimitRowsNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"count": "not-a-number"})


def test_execute_limits_rows():
    node = LimitRowsNode()
    result = node.execute(_fdf(), {"count": 2})
    assert list(result.df["id"]) == [1, 2]
    assert result.total_row_count == 2


def test_execute_count_larger_than_data():
    node = LimitRowsNode()
    result = node.execute(_fdf(), {"count": 100})
    assert result.total_row_count == 5


def test_to_excel_formula_is_none():
    node = LimitRowsNode()
    assert node.to_excel_formula("RANGE", {"count": 5}) is None
