import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.aggregate.group_by_aggregate import GroupByAggregateNode
from app.nodes.base import SchemaValidationError


def _fdf():
    schema = DataSchema(columns=[
        Column(name="region", type=DataType.STRING),
        Column(name="sales", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({
        "region": ["East", "East", "West", "West", "West"],
        "sales": [10, 20, 5, 15, 25],
    })
    return FluxDataFrame(schema=schema, df=df, total_row_count=5)


def test_infer_output_schema_missing_group_column_raises():
    node = GroupByAggregateNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"group_column": "missing", "aggregations": []})


def test_infer_output_schema_no_aggregations_raises():
    node = GroupByAggregateNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"group_column": "region", "aggregations": []})


def test_infer_output_schema_unknown_column_raises():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "missing", "function": "SUM"}]}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_infer_output_schema_unknown_function_raises():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "MODE"}]}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_infer_output_schema_builds_output_columns():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [
        {"column": "sales", "function": "SUM"}, {"column": "sales", "function": "MIN"},
    ]}
    result = node.infer_output_schema(_fdf().schema, config)
    assert result.column_names() == ["region", "sales_sum", "sales_min"]
    assert result.get_column("sales_sum").type == DataType.NUMBER
    assert result.get_column("sales_min").type == DataType.NUMBER  # sales is numeric


def test_infer_output_schema_duplicate_output_name_raises():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [
        {"column": "sales", "function": "SUM"}, {"column": "sales", "function": "SUM"},
    ]}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, config)


def test_execute_sum():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "SUM"}]}
    result = node.execute(_fdf(), config)
    lookup = dict(zip(result.df["region"], result.df["sales_sum"]))
    assert lookup == {"East": 30, "West": 45}


def test_execute_average():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "AVERAGE"}]}
    result = node.execute(_fdf(), config)
    lookup = dict(zip(result.df["region"], result.df["sales_average"]))
    assert lookup["East"] == 15.0


def test_execute_count_distinct():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "COUNT_DISTINCT"}]}
    result = node.execute(_fdf(), config)
    lookup = dict(zip(result.df["region"], result.df["sales_count_distinct"]))
    assert lookup == {"East": 2, "West": 3}


def test_execute_multiple_aggregations():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [
        {"column": "sales", "function": "SUM"}, {"column": "sales", "function": "MAX"},
    ]}
    result = node.execute(_fdf(), config)
    assert list(result.df.columns) == ["region", "sales_sum", "sales_max"]


def test_to_excel_formula_sum():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "SUM"}]}
    formula = node.to_excel_formula("RANGE", config)
    assert formula == "SUMIF([region], UNIQUE([region]), [sales])"


def test_to_excel_formula_count():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "COUNT"}]}
    formula = node.to_excel_formula("RANGE", config)
    assert formula == "COUNTIF([region], UNIQUE([region]))"


def test_to_excel_formula_min():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "MIN"}]}
    formula = node.to_excel_formula("RANGE", config)
    assert formula == "MINIFS([sales], [region], UNIQUE([region]))"


def test_to_excel_formula_count_distinct_is_none():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [{"column": "sales", "function": "COUNT_DISTINCT"}]}
    assert node.to_excel_formula("RANGE", config) is None


def test_to_excel_formula_explanation_notes_extra_aggregations():
    node = GroupByAggregateNode()
    config = {"group_column": "region", "aggregations": [
        {"column": "sales", "function": "SUM"}, {"column": "sales", "function": "MAX"},
    ]}
    explanation = node.to_excel_formula_explanation(config)
    assert "aren't reflected" in explanation
