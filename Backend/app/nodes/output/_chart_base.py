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
        # Chart rendering happens entirely in the frontend (Recharts) using this node's
        # config plus the upstream preview data — the backend just passes the data through.
        # Because there's no work to do here, an invalid config would otherwise sail through
        # and leave the user staring at a blank chart with a green node; validate the axis
        # columns against the real input so a stale/renamed column is reported as an error.
        # DAGExecutor also calls infer_output_schema before execute(), so this is belt and
        # braces for direct callers, not the only line of defence.
        self.infer_output_schema(input_df.schema, config)
        return input_df

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        return "Charts are visual outputs and aren't part of the generated formula."
