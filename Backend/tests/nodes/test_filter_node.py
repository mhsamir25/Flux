import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.filter_node import FilterNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({"name": ["Alice", "Bob", "Carol", ""], "age": [30, 25, 40, None]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=4)


def test_infer_output_schema_identical_to_input():
    node = FilterNode()
    fdf = _fdf()
    result = node.infer_output_schema(fdf.schema, {"column": "age"})
    assert result is fdf.schema


def test_infer_output_schema_missing_column_raises():
    node = FilterNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"column": "missing"})


def test_execute_numeric_greater_than():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "age", "operator": ">", "value": "28"})
    assert list(result.df["name"]) == ["Alice", "Carol"]
    assert result.total_row_count == 2


def test_execute_equals_string():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "name", "operator": "=", "value": "Bob"})
    assert list(result.df["name"]) == ["Bob"]


def test_execute_contains():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "name", "operator": "contains", "value": "a"})
    assert list(result.df["name"]) == ["Carol"]


def test_execute_starts_with():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "name", "operator": "starts_with", "value": "A"})
    assert list(result.df["name"]) == ["Alice"]


def test_execute_is_empty():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "name", "operator": "is_empty"})
    assert list(result.df["name"]) == [""]


def test_execute_is_not_empty():
    node = FilterNode()
    result = node.execute(_fdf(), {"column": "name", "operator": "is_not_empty"})
    assert list(result.df["name"]) == ["Alice", "Bob", "Carol"]


def test_execute_second_condition_and():
    node = FilterNode()
    config = {
        "column": "age", "operator": ">", "value": "20",
        "column2": "name", "operator2": "=", "value2": "Bob",
        "logic": "AND",
    }
    result = node.execute(_fdf(), config)
    assert list(result.df["name"]) == ["Bob"]


def test_execute_second_condition_or():
    node = FilterNode()
    config = {
        "column": "name", "operator": "=", "value": "Alice",
        "column2": "name", "operator2": "=", "value2": "Bob",
        "logic": "OR",
    }
    result = node.execute(_fdf(), config)
    assert set(result.df["name"]) == {"Alice", "Bob"}


def test_execute_invalid_numeric_comparison_raises():
    node = FilterNode()
    with pytest.raises(ValueError):
        node.execute(_fdf(), {"column": "age", "operator": ">", "value": "not-a-number"})


def test_to_excel_formula_comparison():
    node = FilterNode()
    formula = node.to_excel_formula("Sheet1!A1:Z1000", {"column": "age", "operator": ">", "value": "30"})
    assert formula == "FILTER(Sheet1!A1:Z1000, [age]>30)"


def test_to_excel_formula_is_empty():
    node = FilterNode()
    formula = node.to_excel_formula("RANGE", {"column": "name", "operator": "is_empty"})
    assert formula == 'FILTER(RANGE, [name]="")'


def test_to_excel_formula_explanation():
    node = FilterNode()
    explanation = node.to_excel_formula_explanation({"column": "age", "operator": ">", "value": "30"})
    assert "age" in explanation and ">" in explanation
