import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.add_calculated_column import (
    AddCalculatedColumnNode,
    ExpressionSyntaxError,
    evaluate_expression,
    parse_expression,
)


def _fdf():
    schema = DataSchema(columns=[
        Column(name="price", type=DataType.NUMBER),
        Column(name="quantity", type=DataType.NUMBER),
        Column(name="name", type=DataType.STRING),
    ])
    df = pd.DataFrame({"price": [100.0, 50.0], "quantity": [2, 3], "name": ["a", "b"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=2)


# --- expression parser/evaluator (unit-level) -----------------------------------

def test_parse_and_evaluate_arithmetic():
    df = _fdf().df
    ast = parse_expression("price * quantity + 10")
    assert list(evaluate_expression(ast, df)) == [210.0, 160.0]


def test_parse_and_evaluate_if():
    df = _fdf().df
    ast = parse_expression("IF(price > 60, price, 0)")
    result = list(evaluate_expression(ast, df))
    assert result == [100.0, 0.0]


def test_parse_and_evaluate_concat():
    df = _fdf().df
    ast = parse_expression('name & "-x"')
    assert list(evaluate_expression(ast, df)) == ["a-x", "b-x"]


def test_parse_bracket_column_ref():
    df = _fdf().df
    ast = parse_expression("[price] / 2")
    assert list(evaluate_expression(ast, df)) == [50.0, 25.0]


def test_parse_literal_only_expression():
    df = _fdf().df
    ast = parse_expression("1 + 2")
    assert evaluate_expression(ast, df) == 3.0


def test_parse_empty_expression_raises():
    with pytest.raises(ExpressionSyntaxError):
        parse_expression("")


def test_parse_incomplete_expression_raises():
    with pytest.raises(ExpressionSyntaxError):
        parse_expression("price +")


def test_parse_invalid_character_raises():
    with pytest.raises(ExpressionSyntaxError):
        parse_expression("price @ quantity")


def test_parse_unclosed_paren_raises():
    with pytest.raises(ExpressionSyntaxError):
        parse_expression("(price + 1")


def test_evaluate_unknown_column_raises():
    df = _fdf().df
    ast = parse_expression("missing_col + 1")
    with pytest.raises(ValueError):
        evaluate_expression(ast, df)


# --- node-level -----------------------------------------------------------------

def test_infer_output_schema_arithmetic_is_number():
    node = AddCalculatedColumnNode()
    result = node.infer_output_schema(_fdf().schema, {
        "new_column_name": "total", "expression": "price * quantity",
    })
    assert result.get_column("total").type == DataType.NUMBER


def test_infer_output_schema_concat_is_string():
    node = AddCalculatedColumnNode()
    result = node.infer_output_schema(_fdf().schema, {
        "new_column_name": "label", "expression": 'name & "!"',
    })
    assert result.get_column("label").type == DataType.STRING


def test_infer_output_schema_comparison_is_boolean():
    node = AddCalculatedColumnNode()
    result = node.infer_output_schema(_fdf().schema, {
        "new_column_name": "flag", "expression": "price > 10",
    })
    assert result.get_column("flag").type == DataType.BOOLEAN


def test_infer_output_schema_missing_name_raises():
    node = AddCalculatedColumnNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"expression": "price + 1"})


def test_infer_output_schema_duplicate_name_raises():
    node = AddCalculatedColumnNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"new_column_name": "price", "expression": "1"})


def test_infer_output_schema_bad_expression_raises():
    node = AddCalculatedColumnNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"new_column_name": "x", "expression": "price +"})


def test_infer_output_schema_unknown_column_raises():
    node = AddCalculatedColumnNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"new_column_name": "x", "expression": "missing_col + 1"})


def test_execute_adds_computed_column():
    node = AddCalculatedColumnNode()
    result = node.execute(_fdf(), {"new_column_name": "total", "expression": "price * quantity"})
    assert list(result.df["total"]) == [200.0, 150.0]
    assert result.schema.column_names() == ["price", "quantity", "name", "total"]


def test_execute_with_if_expression():
    node = AddCalculatedColumnNode()
    result = node.execute(_fdf(), {
        "new_column_name": "discounted",
        "expression": "IF(price > 60, price * 0.9, price)",
    })
    assert list(result.df["discounted"]) == [90.0, 50.0]


def test_to_excel_formula_composes_expression_tree():
    node = AddCalculatedColumnNode()
    formula = node.to_excel_formula(None, {"new_column_name": "total", "expression": "price * quantity"})
    assert formula == "([price]*[quantity])"


def test_to_excel_formula_none_without_expression():
    node = AddCalculatedColumnNode()
    assert node.to_excel_formula(None, {"new_column_name": "x"}) is None


def test_to_excel_formula_none_on_invalid_expression():
    node = AddCalculatedColumnNode()
    assert node.to_excel_formula(None, {"new_column_name": "x", "expression": "price +"}) is None
