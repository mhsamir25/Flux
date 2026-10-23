from typing import Optional

from app.csv_io.parser import FileParsingError
from app.csv_io.xlsx_io import parse_xlsx
from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class ReadXlsxNode(NodePlugin):
    id = "read_xlsx"
    display_name = "Read XLSX"
    category = NodeCategory.SOURCE
    input_ports = 0
    output_ports = 1

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(
                key="sheet_name",
                label="Sheet Name",
                type=FieldType.TEXT,
                placeholder="Defaults to the first sheet",
                required=False,
            )
        ]

    def infer_output_schema(self, input_schema: Optional[DataSchema], config: dict) -> DataSchema:
        # Real schema only known once the workbook is actually parsed in execute_source().
        return DataSchema(columns=[])

    def execute(self, input_df, config):
        raise NotImplementedError("read_xlsx is a source node; use execute_source() instead")

    def execute_source(self, config: dict) -> FluxDataFrame:
        raw = config.get("_xlsx_bytes")
        if raw is None:
            raise SchemaValidationError("No XLSX data available for this Read XLSX node.")
        sheet_name = (config.get("sheet_name") or "").strip() or None
        try:
            return parse_xlsx(raw, sheet_name=sheet_name)
        except FileParsingError as e:
            raise SchemaValidationError(str(e)) from e

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return "Sheet1!A1:Z1000"

    def requires_reparse(self, config: dict) -> bool:
        """A sheet_name can only be honoured by re-parsing the workbook from its raw bytes.
        Without this, the executor hands back the frame parsed at upload time — which was
        parsed from whichever sheet the upload defaulted to — and the node's sheet_name is
        silently ignored.
        """
        return bool((config.get("sheet_name") or "").strip())

    def to_excel_formula_explanation(self, config: dict) -> str:
        return (
            "Reads data from Sheet1!A1:Z1000 — adjust this range in Excel to match "
            "your actual data's extent."
        )
