from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class ChartNode(NodePlugin):
    category = NodeCategory.OUTPUT
    formula_exportable = False

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="x_column", label="X Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="y_column", label="Y Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="title", label="Title", type=FieldType.TEXT, required=False),
            FieldSchema(key="color", label="Color", type=FieldType.COLOR_PICKER, required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        for label in ("x_column", "y_column"):
            column = config.get(label)
            if not column or not input_schema.has_column(column):
                raise SchemaValidationError(f"Column '{column}' not found in the input data.")
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        self.infer_output_schema(input_df.schema, config)
        return input_df

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        return "Charts are visual outputs and aren't part of the generated formula."
