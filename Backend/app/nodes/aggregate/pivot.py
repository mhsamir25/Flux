from typing import Optional

import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.aggregate.group_by_aggregate import AGGREGATE_FUNCTIONS, PANDAS_FUNC_MAP
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class PivotNode(NodePlugin):
    id = "pivot"
    display_name = "Pivot"
    category = NodeCategory.AGGREGATE
    formula_exportable = False

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="row_column", label="Row Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="column_column", label="Column Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="value_column", label="Value Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="aggregate_function", label="Aggregate Function", type=FieldType.ENUM,
                        options=AGGREGATE_FUNCTIONS),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        for label in ("row_column", "column_column", "value_column"):
            col = config.get(label)
            if not col or not input_schema.has_column(col):
                raise SchemaValidationError(f"Column '{col}' not found in the input data.")
        function = config.get("aggregate_function")
        if function not in AGGREGATE_FUNCTIONS:
            raise SchemaValidationError(f"Unsupported aggregation function '{function}'.")
        # Real output columns (one per distinct value_column value) are only known post-execution.
        return DataSchema(columns=[input_schema.get_column(config["row_column"])])

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        row_column = config.get("row_column")
        column_column = config.get("column_column")
        value_column = config.get("value_column")
        function = config.get("aggregate_function")
        pandas_func = PANDAS_FUNC_MAP.get(function)
        if not row_column or not column_column or not value_column:
            raise ValueError("Pivot requires a row column, column column, and value column.")
        if pandas_func is None:
            raise ValueError(f"Unsupported aggregation function '{function}'.")
        pivoted = input_df.df.pivot_table(
            index=row_column, columns=column_column, values=value_column, aggfunc=pandas_func,
            dropna=False,
        )
        pivoted = pivoted.reset_index()
        pivoted.columns = [_label_for(c, row_column) for c in pivoted.columns]

        columns = [Column(name=name, type=_dtype_to_data_type(pivoted[name].dtype), nullable=True)
                   for name in pivoted.columns]
        schema = DataSchema(columns=columns)
        return FluxDataFrame(schema=schema, df=pivoted, total_row_count=len(pivoted))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        return "Pivot tables aren't formula-driven in Excel — this step can't be exported as a formula."


def _label_for(column_label, row_column: str) -> str:
    """Column label for a pivoted frame, giving a missing category a readable name.

    With dropna=False a null category now survives as a column whose label is NaN; str(nan)
    would put a literal "nan" column in the output, which then shows up that way in the
    preview table and the column picker. "(blank)" says what it actually is.
    """
    if pd.isna(column_label):
        return "(blank)"
    return str(column_label)


def _dtype_to_data_type(dtype) -> DataType:
    if pd.api.types.is_bool_dtype(dtype):
        return DataType.BOOLEAN
    if pd.api.types.is_numeric_dtype(dtype):
        return DataType.NUMBER
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return DataType.DATE
    return DataType.STRING
