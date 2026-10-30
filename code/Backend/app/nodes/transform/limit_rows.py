from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class LimitRowsNode(NodePlugin):
    id = "limit_rows"
    display_name = "Limit Rows"
    category = NodeCategory.TRANSFORM
    formula_exportable = False

    def get_config_schema(self) -> list[FieldSchema]:
        return [FieldSchema(key="count", label="Row Count", type=FieldType.NUMBER)]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        count = config.get("count")
        if count is None:
            raise SchemaValidationError("Limit Rows requires a row count.")
        try:
            if int(count) < 0:
                raise SchemaValidationError("Limit Rows requires a non-negative row count.")
        except (TypeError, ValueError):
            raise SchemaValidationError(f"'{count}' is not a valid row count.")
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        count = int(config.get("count", 0))
        df = input_df.df.head(count).reset_index(drop=True)
        return FluxDataFrame(schema=input_df.schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        count = config.get("count", "?")
        return f"Keep only the first {count} rows. (No Excel formula equivalent for row limiting.)"
