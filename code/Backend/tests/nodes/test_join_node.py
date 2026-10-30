import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import NodeCategory, SchemaValidationError
from app.nodes.join.join_node import JoinNode


def _left():
    schema = DataSchema(columns=[
        Column(name="id", type=DataType.NUMBER),
        Column(name="name", type=DataType.STRING),
    ])
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Carol"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def _right():
    schema = DataSchema(columns=[
        Column(name="id", type=DataType.NUMBER),
        Column(name="dept", type=DataType.STRING),
    ])
    df = pd.DataFrame({"id": [1, 2, 4], "dept": ["Eng", "Sales", "HR"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def _right_with_overlap():
    # 'name' collides with left's 'name', on a different key column ('rid')
    schema = DataSchema(columns=[
        Column(name="rid", type=DataType.NUMBER),
        Column(name="name", type=DataType.STRING),
    ])
    df = pd.DataFrame({"rid": [1, 2, 4], "name": ["EngName", "SalesName", "HRName"]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=3)


def test_id_and_category_and_ports():
    node = JoinNode()
    assert node.id == "join"
    assert node.category == NodeCategory.JOIN
    assert node.input_ports == 2
    assert node.output_ports == 1


def test_execute_raises_not_implemented():
    node = JoinNode()
    with pytest.raises(NotImplementedError):
        node.execute(None, {})


def test_infer_output_schema_missing_right_schema_raises():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "INNER"}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_left().schema, config)


def test_infer_output_schema_missing_left_key_raises():
    node = JoinNode()
    config = {"left_key": "missing", "right_key": "id", "join_type": "INNER",
              "_right_schema": _right().schema}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_left().schema, config)


def test_infer_output_schema_missing_right_key_raises():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "missing", "join_type": "INNER",
              "_right_schema": _right().schema}
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_left().schema, config)


def test_infer_output_schema_same_key_name_dedupes():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "INNER", "_right_schema": _right().schema}
    result = node.infer_output_schema(_left().schema, config)
    assert result.column_names() == ["id", "name", "dept"]


def test_infer_output_schema_overlapping_non_key_columns_suffixed():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "rid", "join_type": "LEFT",
              "_right_schema": _right_with_overlap().schema}
    result = node.infer_output_schema(_left().schema, config)
    assert result.column_names() == ["id", "name_left", "rid", "name_right"]


def test_execute_join_inner():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "INNER"}
    result = node.execute_join(_left(), _right(), config)
    assert list(result.df.columns) == ["id", "name", "dept"]
    assert result.total_row_count == 2  # ids 1,2 match
    assert set(result.df["id"]) == {1, 2}


def test_execute_join_left():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "LEFT"}
    result = node.execute_join(_left(), _right(), config)
    assert result.total_row_count == 3  # all left rows kept
    carol_row = result.df[result.df["name"] == "Carol"].iloc[0]
    assert pd.isna(carol_row["dept"])


def test_execute_join_right():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "RIGHT"}
    result = node.execute_join(_left(), _right(), config)
    assert result.total_row_count == 3  # all right rows kept


def test_execute_join_full():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "FULL"}
    result = node.execute_join(_left(), _right(), config)
    assert result.total_row_count == 4  # 1,2 matched, 3 left-only, 4 right-only


def test_execute_join_schema_matches_actual_columns():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "rid", "join_type": "LEFT"}
    result = node.execute_join(_left(), _right_with_overlap(), config)
    assert result.schema.column_names() == list(result.df.columns)


def test_execute_join_unknown_key_raises():
    node = JoinNode()
    config = {"left_key": "missing", "right_key": "id", "join_type": "INNER"}
    with pytest.raises(ValueError):
        node.execute_join(_left(), _right(), config)


def test_to_excel_formula_left():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "LEFT"}
    formula = node.to_excel_formula("RANGE", config)
    assert formula == "XLOOKUP([id], [Right!id], [Right!*])"


def test_to_excel_formula_right_join_is_none():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "RIGHT"}
    assert node.to_excel_formula("RANGE", config) is None


def test_to_excel_formula_full_join_is_none():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "FULL"}
    assert node.to_excel_formula("RANGE", config) is None


def test_to_excel_formula_explanation_right_join_notes_no_equivalent():
    node = JoinNode()
    config = {"left_key": "id", "right_key": "id", "join_type": "RIGHT"}
    explanation = node.to_excel_formula_explanation(config)
    assert "No Excel formula equivalent" in explanation
