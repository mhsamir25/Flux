import math

import pandas as pd
import pytest

from app.dataframe.schema import Column, DataSchema, DataType
from app.dataframe.frame import FluxDataFrame
from app.dataframe.inference import infer_cell_type, infer_column_type




def _schema():
    return DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
    ])


def test_has_column():
    schema = _schema()
    assert schema.has_column("name")
    assert not schema.has_column("missing")


def test_get_column():
    schema = _schema()
    col = schema.get_column("age")
    assert col.type == DataType.NUMBER


def test_get_column_missing_raises_keyerror():
    schema = _schema()
    with pytest.raises(KeyError):
        schema.get_column("missing")


def test_column_names():
    schema = _schema()
    assert schema.column_names() == ["name", "age"]



def _flux_df():
    schema = _schema()
    df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"], "age": [30, 25, 40]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def test_preview_truncates_rows_but_keeps_total_row_count():
    fdf = _flux_df()
    preview = fdf.preview(2)
    assert len(preview.df) == 2
    assert preview.total_row_count == 3


def test_preview_does_not_mutate_original():
    fdf = _flux_df()
    fdf.preview(1)
    assert len(fdf.df) == 3


def test_with_schema_replaces_schema_keeps_data():
    fdf = _flux_df()
    new_schema = DataSchema(columns=[Column(name="name", type=DataType.STRING)])
    updated = fdf.with_schema(new_schema)
    assert updated.schema is new_schema
    assert len(updated.df) == 3


def test_add_column_appends_schema_and_values():
    fdf = _flux_df()
    updated = fdf.add_column("passed", DataType.BOOLEAN, pd.Series([True, False, True]))
    assert updated.schema.column_names() == ["name", "age", "passed"]
    assert list(updated.df["passed"]) == [True, False, True]
    # original untouched
    assert "passed" not in fdf.df.columns


def test_to_json_records_converts_nan_to_none():
    schema = DataSchema(columns=[Column(name="x", type=DataType.NUMBER)])
    df = pd.DataFrame({"x": [1, float("nan"), 3]})
    fdf = FluxDataFrame(schema=schema, df=df, total_row_count=3)
    records = fdf.to_json_records()
    assert records == [{"x": 1}, {"x": None}, {"x": 3}]


def test_to_json_records_empty_frame():
    fdf = FluxDataFrame(schema=DataSchema(columns=[]), df=pd.DataFrame(), total_row_count=0)
    assert fdf.to_json_records() == []



@pytest.mark.parametrize("value,expected", [
    ("42", DataType.NUMBER),
    ("3.14", DataType.NUMBER),
    ("2026-01-15", DataType.DATE),
    ("01/15/2026", DataType.DATE),
    ("true", DataType.BOOLEAN),
    ("Yes", DataType.BOOLEAN),
    ("hello", DataType.STRING),
])
def test_infer_cell_type(value, expected):
    assert infer_cell_type(value) == expected


def test_infer_cell_type_blank_is_none():
    assert infer_cell_type(None) is None
    assert infer_cell_type("") is None
    assert infer_cell_type("   ") is None


def test_infer_cell_type_numeric_wins_over_boolean_for_1_and_0():
    # documented tradeoff: numeric check runs before boolean check
    assert infer_cell_type("1") == DataType.NUMBER
    assert infer_cell_type("0") == DataType.NUMBER


def test_infer_column_type_consistent_numbers():
    assert infer_column_type(["1", "2", "3"]) == DataType.NUMBER


def test_infer_column_type_consistent_dates():
    assert infer_column_type(["2026-01-01", "2026-02-01"]) == DataType.DATE


def test_infer_column_type_mixed_falls_back_to_string():
    assert infer_column_type(["1", "hello", "2026-01-01"]) == DataType.STRING


def test_infer_column_type_ignores_blanks():
    assert infer_column_type(["1", "", None, "2"]) == DataType.NUMBER


def test_infer_column_type_all_blank_defaults_string():
    assert infer_column_type(["", None, "  "]) == DataType.STRING
