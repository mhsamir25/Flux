from typing import Optional

import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema, DataType
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError

_STRATEGIES = ["fixed", "average", "median", "previous"]
_REDUCTION_STRATEGIES = ("average", "median")
_REDUCIBLE_TYPES = (DataType.NUMBER, DataType.BOOLEAN, DataType.DATE)


class FillMissingNode(NodePlugin):
    id = "fill_missing"
    display_name = "Fill Missing"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="strategy", label="Strategy", type=FieldType.ENUM, options=_STRATEGIES),
            FieldSchema(key="fixed_value", label="Fixed Value", type=FieldType.TEXT, required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        column = config.get("column")
        if not column or not input_schema.has_column(column):
            raise SchemaValidationError(f"Column '{column}' not found in the input data.")
        strategy = config.get("strategy")
        if strategy not in _STRATEGIES:
            raise SchemaValidationError(f"Unknown fill strategy '{strategy}'.")
        if strategy in _REDUCTION_STRATEGIES:
            if input_schema.get_column(column).type not in _REDUCIBLE_TYPES:
                raise SchemaValidationError(
                    f"Cannot fill missing values in column '{column}' with the '{strategy}' "
                    f"strategy: that strategy only works on numeric columns, and '{column}' "
                    f"is a text column. Use the 'fixed' or 'previous' strategy instead."
                )
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        column = config.get("column")
        strategy = config.get("strategy")
        # Validate before touching the data, so an inapplicable strategy fails with the
        # node's own message instead of whatever pandas raises mid-reduction.
        self.infer_output_schema(input_df.schema, config)
        df = input_df.df.copy()
        series = df[column]

        if strategy == "fixed":
            df[column] = series.fillna(_cast_fixed_value(series, config.get("fixed_value")))
        elif strategy == "average":
            df[column] = series.fillna(series.mean())
        elif strategy == "median":
            df[column] = series.fillna(series.median())
        elif strategy == "previous":
            df[column] = series.ffill()
        else:
            raise ValueError(f"Unknown fill strategy '{strategy}'.")

        return FluxDataFrame(schema=input_df.schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        column_ref = f"[{config.get('column') or '?'}]"
        strategy = config.get("strategy")
        if strategy == "fixed":
            fixed_value = config.get("fixed_value", "")
            value_literal = fixed_value if _looks_numeric(fixed_value) else f'"{fixed_value}"'
        elif strategy == "average":
            value_literal = f"AVERAGE({column_ref})"
        elif strategy == "median":
            value_literal = f"MEDIAN({column_ref})"
        else:  # "previous" has no simple single-formula Excel equivalent
            return None
        return f"IF(ISBLANK({column_ref}), {value_literal}, {column_ref})"

    def to_excel_formula_explanation(self, config: dict) -> str:
        column = config.get("column", "?")
        strategy = config.get("strategy", "?")
        if strategy == "previous":
            return (
                f"Fill missing values in {column} by carrying forward the previous value. "
                "(No simple Excel formula equivalent for this strategy.)"
            )
        return f"Fill missing values in {column} using the '{strategy}' strategy."


def _cast_fixed_value(series, raw_value):
    if pd.api.types.is_numeric_dtype(series):
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"'{raw_value}' is not a valid number for column '{series.name}'.")
    return raw_value


def _looks_numeric(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
