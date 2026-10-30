from typing import Optional

from app.csv_io.parser import FileParsingError, parse_csv
from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, NodeCategory, NodePlugin, SchemaValidationError


class ReadCsvNode(NodePlugin):
    id = "read_csv"
    display_name = "Read CSV"
    category = NodeCategory.SOURCE
    input_ports = 0
    output_ports = 1

    def get_config_schema(self) -> list[FieldSchema]:
        return []

    def infer_output_schema(self, input_schema: Optional[DataSchema], config: dict) -> DataSchema:
        # A source's real schema is only known once the file is actually parsed in
        # execute_source() — there's no upstream schema and no config to infer from here.
        return DataSchema(columns=[])

    def execute(self, input_df, config):
        raise NotImplementedError("read_csv is a source node; use execute_source() instead")

    def execute_source(self, config: dict) -> FluxDataFrame:
        raw = config.get("_csv_text")
        if raw is None:
            raise SchemaValidationError("No CSV data available for this Read CSV node.")
        try:
            return parse_csv(raw)
        except FileParsingError as e:
            raise SchemaValidationError(str(e)) from e

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return "Sheet1!A1:Z1000"

    def to_excel_formula_explanation(self, config: dict) -> str:
        return (
            "Reads data from Sheet1!A1:Z1000 — adjust this range in Excel to match "
            "your actual data's extent."
        )
