import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.convert_type import ConvertTypeNode


def _fdf():
    schema = DataSchema(columns=[Column(name="value", type=DataType.STRING)])
    df = pd.DataFrame({"value": ["10", "20", "not-a-number"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def test_infer_output_schema_unsupported_target_raises():
    node = ConvertTypeNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"column": "value", "target_type": "BOOLEAN"})


def test_infer_output_schema_updates_column_type():
    node = ConvertTypeNode()
    result = node.infer_output_schema(_fdf().schema, {"column": "value", "target_type": "NUMBER"})
    assert result.get_column("value").type == DataType.NUMBER


def test_execute_convert_to_number_coerces_failures_to_null():
    node = ConvertTypeNode()
    result = node.execute(_fdf(), {"column": "value", "target_type": "NUMBER"})
    values = list(result.df["value"])
    assert values[0] == 10.0
    assert values[1] == 20.0
    assert pd.isna(values[2])


def test_execute_convert_to_date():
    schema = DataSchema(columns=[Column(name="d", type=DataType.STRING)])
    df = pd.DataFrame({"d": ["2026-01-15", "not-a-date"]})
    fdf = FluxDataFrame(schema=schema, df=df, total_row_count=2)
    node = ConvertTypeNode()
    result = node.execute(fdf, {"column": "d", "target_type": "DATE"})
    assert pd.notna(result.df["d"].iloc[0])
    assert pd.isna(result.df["d"].iloc[1])


def test_execute_convert_to_string():
    schema = DataSchema(columns=[Column(name="n", type=DataType.NUMBER)])
    df = pd.DataFrame({"n": [1, 2]})
    fdf = FluxDataFrame(schema=schema, df=df, total_row_count=2)
    node = ConvertTypeNode()
    result = node.execute(fdf, {"column": "n", "target_type": "STRING"})
    assert list(result.df["n"]) == ["1", "2"]


def test_to_excel_formula_number():
    node = ConvertTypeNode()
    assert node.to_excel_formula("RANGE", {"column": "value", "target_type": "NUMBER"}) == "VALUE([value])"


def test_to_excel_formula_string():
    node = ConvertTypeNode()
    assert node.to_excel_formula("RANGE", {"column": "value", "target_type": "STRING"}) == 'TEXT([value], "@")'


def test_to_excel_formula_date():
    node = ConvertTypeNode()
    assert node.to_excel_formula("RANGE", {"column": "value", "target_type": "DATE"}) == "DATEVALUE([value])"
