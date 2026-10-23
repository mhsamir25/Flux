from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class RemoveDuplicatesNode(NodePlugin):
    id = "remove_duplicates"
    display_name = "Remove Duplicates"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [FieldSchema(key="columns", label="Match Columns", type=FieldType.MULTI_COLUMN_SELECT, required=False)]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        for c in config.get("columns") or []:
            if not input_schema.has_column(c):
                raise SchemaValidationError(f"Column '{c}' not found in the input data.")
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        columns = config.get("columns") or None  # empty/None -> dedupe on all columns
        df = input_df.df.drop_duplicates(subset=columns).reset_index(drop=True)
        return FluxDataFrame(schema=input_df.schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return f"UNIQUE({input_ref})"

    def to_excel_formula_explanation(self, config: dict) -> str:
        columns = config.get("columns") or []
        if columns:
            return (
                f"Remove duplicate rows (matched by: {', '.join(columns)}). "
                "Note: Excel's UNIQUE() dedupes on the whole row, not just the selected columns."
            )
        return "Remove duplicate rows."
