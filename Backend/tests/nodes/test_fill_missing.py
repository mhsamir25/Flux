import math

import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.fill_missing import FillMissingNode


def _fdf():
    schema = DataSchema(columns=[Column(name="score", type=DataType.NUMBER)])
    df = pd.DataFrame({"score": [10.0, None, 30.0, None]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=4)


def test_infer_output_schema_unknown_strategy_raises():
    node = FillMissingNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"column": "score", "strategy": "bogus"})


def test_infer_output_schema_missing_column_raises():
    node = FillMissingNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"column": "missing", "strategy": "fixed"})


def test_execute_fixed_strategy():
    node = FillMissingNode()
    result = node.execute(_fdf(), {"column": "score", "strategy": "fixed", "fixed_value": "0"})
    assert list(result.df["score"]) == [10.0, 0.0, 30.0, 0.0]


def test_execute_average_strategy():
    node = FillMissingNode()
    result = node.execute(_fdf(), {"column": "score", "strategy": "average"})
    assert list(result.df["score"]) == [10.0, 20.0, 30.0, 20.0]


def test_execute_median_strategy():
    node = FillMissingNode()
    result = node.execute(_fdf(), {"column": "score", "strategy": "median"})
    assert list(result.df["score"]) == [10.0, 20.0, 30.0, 20.0]


def test_execute_previous_strategy():
    node = FillMissingNode()
    result = node.execute(_fdf(), {"column": "score", "strategy": "previous"})
    assert list(result.df["score"]) == [10.0, 10.0, 30.0, 30.0]


def test_to_excel_formula_fixed():
    node = FillMissingNode()
    formula = node.to_excel_formula("RANGE", {"column": "score", "strategy": "fixed", "fixed_value": "0"})
    assert formula == "IF(ISBLANK([score]), 0, [score])"


def test_to_excel_formula_average():
    node = FillMissingNode()
    formula = node.to_excel_formula("RANGE", {"column": "score", "strategy": "average"})
    assert formula == "IF(ISBLANK([score]), AVERAGE([score]), [score])"


def test_to_excel_formula_previous_is_none():
    node = FillMissingNode()
    assert node.to_excel_formula("RANGE", {"column": "score", "strategy": "previous"}) is None
