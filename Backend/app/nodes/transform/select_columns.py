from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class SelectColumnsNode(NodePlugin):
    id = "select_columns"
    display_name = "Select Columns"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [FieldSchema(key="columns", label="Columns", type=FieldType.MULTI_COLUMN_SELECT)]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        columns = config.get("columns") or []
        if not columns:
            raise SchemaValidationError("Select Columns requires at least one column to be selected.")
        for c in columns:
            if not input_schema.has_column(c):
                raise SchemaValidationError(f"Column '{c}' not found in the input data.")
        return DataSchema(columns=[input_schema.get_column(c) for c in columns])

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        columns = config.get("columns") or []
        df = input_df.df[columns].reset_index(drop=True)
        schema = DataSchema(columns=[input_df.schema.get_column(c) for c in columns])
        return FluxDataFrame(schema=schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        columns = config.get("columns") or []
        if not columns:
            return None
        refs = ", ".join(f"[{c}]" for c in columns)
        return f"CHOOSECOLS({input_ref}, {refs})"

    def to_excel_formula_explanation(self, config: dict) -> str:
        columns = config.get("columns") or []
        return f"Keep only these columns: {', '.join(columns)}." if columns else "Select columns."
