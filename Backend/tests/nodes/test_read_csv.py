import pytest

from app.nodes.base import NodeCategory, SchemaValidationError
from app.nodes.source.read_csv import ReadCsvNode


def test_id_and_category():
    node = ReadCsvNode()
    assert node.id == "read_csv"
    assert node.category == NodeCategory.SOURCE
    assert node.input_ports == 0
    assert node.output_ports == 1


def test_no_config_fields():
    node = ReadCsvNode()
    assert node.get_config_schema() == []


def test_infer_output_schema_is_empty_placeholder():
    node = ReadCsvNode()
    schema = node.infer_output_schema(None, {})
    assert schema.columns == []


def test_execute_raises_not_implemented():
    node = ReadCsvNode()
    with pytest.raises(NotImplementedError):
        node.execute(None, {})


def test_execute_source_missing_data_raises_schema_validation_error():
    node = ReadCsvNode()
    with pytest.raises(SchemaValidationError):
        node.execute_source({})


def test_execute_source_parses_injected_csv_text():
    node = ReadCsvNode()
    fdf = node.execute_source({"_csv_text": "name,age\nAlice,30\nBob,25"})
    assert fdf.total_row_count == 2
    assert fdf.schema.column_names() == ["name", "age"]
    assert fdf.df.iloc[0]["name"] == "Alice"


def test_execute_source_wraps_parsing_error_as_schema_validation_error(monkeypatch):
    import app.nodes.source.read_csv as module

    def _tiny_cap(data, max_rows=None):
        from app.csv_io.parser import FileParsingError
        raise FileParsingError("too many rows")

    monkeypatch.setattr(module, "parse_csv", _tiny_cap)
    node = ReadCsvNode()
    with pytest.raises(SchemaValidationError):
        node.execute_source({"_csv_text": "a\n1"})


def test_to_excel_formula_placeholder():
    node = ReadCsvNode()
    assert node.to_excel_formula(None, {}) == "Sheet1!A1:Z1000"


def test_to_excel_formula_explanation_mentions_adjusting_range():
    node = ReadCsvNode()
    explanation = node.to_excel_formula_explanation({})
    assert "adjust" in explanation.lower()
