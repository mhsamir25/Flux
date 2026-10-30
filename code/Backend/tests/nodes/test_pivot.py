import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.aggregate.pivot import PivotNode
from app.nodes.base import SchemaValidationError


def _fdf():
    schema = DataSchema(columns=[
        Column(name="region", type=DataType.STRING),
        Column(name="product", type=DataType.STRING),
        Column(name="sales", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({
        "region": ["East", "East", "West", "West"],
        "product": ["A", "B", "A", "B"],
        "sales": [10, 20, 30, 40],
    })
    return FluxDataFrame(schema=schema, df=df, total_row_count=4)


def _config():
    return {
        "row_column": "region", "column_column": "product",
        "value_column": "sales", "aggregate_function": "SUM",
    }


def test_infer_output_schema_missing_column_raises():
    node = PivotNode()
    config = {**_config(), "row_column": "missing"}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_infer_output_schema_unknown_function_raises():
    node = PivotNode()
    config = {**_config(), "aggregate_function": "MODE"}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_infer_output_schema_only_guarantees_row_column():
    node = PivotNode()
    result = node.infer_output_schema(_fdf().schema, _config())
    assert result.column_names() == ["region"]


def test_execute_pivots_data():
    node = PivotNode()
    result = node.execute(_fdf(), _config())
    assert set(result.df.columns) == {"region", "A", "B"}
    row = result.df.set_index("region")
    assert row.loc["East", "A"] == 10
    assert row.loc["West", "B"] == 40


def test_execute_schema_matches_actual_columns():
    node = PivotNode()
    result = node.execute(_fdf(), _config())
    assert set(result.schema.column_names()) == set(result.df.columns)
    assert result.schema.get_column("region").type == DataType.STRING
    assert result.schema.get_column("A").type == DataType.NUMBER


def test_execute_missing_required_column_raises():
    node = PivotNode()
    config = {**_config(), "value_column": None}
    with pytest.raises(ValueError):
        node.execute(_fdf(), config)


def test_to_excel_formula_always_none():
    node = PivotNode()
    assert node.to_excel_formula("RANGE", _config()) is None


def test_to_excel_formula_explanation_mentions_not_formula_driven():
    node = PivotNode()
    explanation = node.to_excel_formula_explanation(_config())
    assert "aren't formula-driven" in explanation
