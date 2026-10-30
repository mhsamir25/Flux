import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.sort_node import SortNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({"name": ["Bob", "Alice", "Carol"], "age": [25, 30, 25]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def test_infer_output_schema_no_keys_raises():
    node = SortNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {})


def test_infer_output_schema_missing_column_raises():
    node = SortNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"column": "missing"})


def test_execute_single_key_asc():
    node = SortNode()
    result = node.execute(_fdf(), {"column": "age", "direction": "ASC"})
    assert list(result.df["age"]) == [25, 25, 30]


def test_execute_single_key_desc():
    node = SortNode()
    result = node.execute(_fdf(), {"column": "age", "direction": "DESC"})
    assert list(result.df["age"]) == [30, 25, 25]


def test_execute_no_direction_defaults_asc():
    node = SortNode()
    result = node.execute(_fdf(), {"column": "age"})
    assert list(result.df["age"]) == [25, 25, 30]


def test_execute_multi_key():
    node = SortNode()
    config = {"sort_keys": [{"column": "age", "direction": "ASC"}, {"column": "name", "direction": "ASC"}]}
    result = node.execute(_fdf(), config)
    # age=25 rows (Bob, Carol) sort before age=30 (Alice); within age=25, name ASC -> Bob before Carol
    assert list(result.df["name"]) == ["Bob", "Carol", "Alice"]


def test_execute_no_keys_raises():
    node = SortNode()
    with pytest.raises(ValueError):
        node.execute(_fdf(), {})


def test_to_excel_formula_primary_key_only():
    node = SortNode()
    formula = node.to_excel_formula("RANGE", {"column": "age", "direction": "DESC"})
    assert formula == "SORT(RANGE, [age], -1)"


def test_to_excel_formula_none_without_keys():
    node = SortNode()
    assert node.to_excel_formula("RANGE", {}) is None


def test_to_excel_formula_explanation_notes_dropped_secondary_keys():
    node = SortNode()
    config = {"sort_keys": [{"column": "age", "direction": "ASC"}, {"column": "name", "direction": "DESC"}]}
    explanation = node.to_excel_formula_explanation(config)
    assert "age" in explanation
    assert "name" in explanation
    assert "aren't reflected" in explanation
