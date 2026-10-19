from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class DataTableNode(NodePlugin):
    id = "data_table"
    display_name = "Data Table"
    category = NodeCategory.OUTPUT

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="columns", label="Columns", type=FieldType.MULTI_COLUMN_SELECT, required=False),
            FieldSchema(key="rows_per_page", label="Rows Per Page", type=FieldType.NUMBER, required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        columns = config.get("columns") or []
        if not columns:
            return input_schema
        for c in columns:
            if not input_schema.has_column(c):
                raise SchemaValidationError(f"Column '{c}' not found in the input data.")
        return DataSchema(columns=[input_schema.get_column(c) for c in columns])

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        columns = config.get("columns") or []
        if not columns:
            return input_df
        df = input_df.df[columns].reset_index(drop=True)
        schema = DataSchema(columns=[input_df.schema.get_column(c) for c in columns])
        return FluxDataFrame(schema=schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return input_ref  # identity wrapper — data_table doesn't transform data structurally

    def to_excel_formula_explanation(self, config: dict) -> str:
        return "Display the data as a table."
