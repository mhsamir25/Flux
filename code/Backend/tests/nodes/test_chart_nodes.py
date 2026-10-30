import pandas as pd
import pytest

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import FieldType, NodeCategory, SchemaValidationError
from app.nodes.output.bar_chart import BarChartNode
from app.nodes.output.line_chart import LineChartNode
from app.nodes.output.pie_chart import PieChartNode

CHART_CLASSES = [BarChartNode, LineChartNode, PieChartNode]


def _fdf():
    schema = DataSchema(columns=[
        Column(name="month", type=DataType.STRING),
        Column(name="revenue", type=DataType.NUMBER),
    ])
    df = pd.DataFrame({"month": ["Jan", "Feb"], "revenue": [100, 200]})
    return FluxDataFrame(schema=schema, df=df, total_row_count=2)


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_category_and_ports(cls):
    node = cls()
    assert node.category == NodeCategory.OUTPUT
    assert node.input_ports == 1


@pytest.mark.parametrize("cls,expected_id,expected_name", [
    (BarChartNode, "bar_chart", "Bar Chart"),
    (LineChartNode, "line_chart", "Line Chart"),
    (PieChartNode, "pie_chart", "Pie Chart"),
])
def test_id_and_display_name(cls, expected_id, expected_name):
    node = cls()
    assert node.id == expected_id
    assert node.display_name == expected_name


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_config_schema_fields(cls):
    node = cls()
    fields = {f.key: f for f in node.get_config_schema()}
    assert set(fields) == {"x_column", "y_column", "title", "color"}
    assert fields["x_column"].type == FieldType.COLUMN_SELECT
    assert fields["color"].type == FieldType.COLOR_PICKER
    assert fields["title"].required is False


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_infer_output_schema_missing_column_raises(cls):
    node = cls()
    with pytest.raises(SchemaValidationError):
        node.infer_output_schema(_fdf().schema, {"x_column": "month", "y_column": "missing"})


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_infer_output_schema_valid_is_identity(cls):
    node = cls()
    fdf = _fdf()
    result = node.infer_output_schema(fdf.schema, {"x_column": "month", "y_column": "revenue"})
    assert result is fdf.schema


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_execute_is_passthrough(cls):
    node = cls()
    fdf = _fdf()
    result = node.execute(fdf, {"x_column": "month", "y_column": "revenue"})
    assert result is fdf


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_to_excel_formula_is_none(cls):
    node = cls()
    assert node.to_excel_formula("RANGE", {}) is None


@pytest.mark.parametrize("cls", CHART_CLASSES)
def test_to_excel_formula_explanation(cls):
    node = cls()
    explanation = node.to_excel_formula_explanation({})
    assert "visual outputs" in explanation
