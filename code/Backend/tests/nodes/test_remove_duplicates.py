import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import SchemaValidationError
from app.nodes.transform.remove_duplicates import RemoveDuplicatesNode


def _fdf():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="city", type=DataType.STRING),
    ])
    df = pd.DataFrame({
        "name": ["Alice", "Alice", "Bob"],
        "city": ["NYC", "LA", "NYC"],
    })
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def test_infer_output_schema_missing_column_raises():
    node = RemoveDuplicatesNode()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"columns": ["missing"]})


def test_execute_dedupe_all_columns():
    node = RemoveDuplicatesNode()
    result = node.execute(_fdf(), {"columns": []})
    assert result.total_row_count == 3  # no exact full-row duplicates


def test_execute_dedupe_by_subset():
    node = RemoveDuplicatesNode()
    result = node.execute(_fdf(), {"columns": ["name"]})
    assert result.total_row_count == 2
    assert list(result.df["name"]) == ["Alice", "Bob"]


def test_to_excel_formula():
    node = RemoveDuplicatesNode()
    assert node.to_excel_formula("RANGE", {}) == "UNIQUE(RANGE)"


def test_to_excel_formula_explanation_notes_whole_row_caveat():
    node = RemoveDuplicatesNode()
    explanation = node.to_excel_formula_explanation({"columns": ["name"]})
    assert "whole row" in explanation
