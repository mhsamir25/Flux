from typing import Optional

import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError

_TARGET_TYPES = ["NUMBER", "STRING", "DATE"]


def _to_datetime_coercing(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    numeric_cells = pd.to_numeric(series, errors="coerce").notna()
    return pd.to_datetime(series.mask(numeric_cells), errors="coerce")


class ConvertTypeNode(NodePlugin):
    id = "convert_type"
    display_name = "Convert Type"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="target_type", label="Target Type", type=FieldType.ENUM, options=_TARGET_TYPES),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        column = config.get("column")
        if not column or not input_schema.has_column(column):
            raise SchemaValidationError(f"Column '{column}' not found in the input data.")
        target_type = config.get("target_type")
        if target_type not in _TARGET_TYPES:
            raise SchemaValidationError(f"Unsupported target type '{target_type}'.")
        new_columns = [
            Column(name=col.name, type=DataType(target_type), nullable=True) if col.name == column else col
            for col in input_schema.columns
        ]
        return DataSchema(columns=new_columns)

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        column = config.get("column")
        target_type = config.get("target_type")
        # Validate the config (and the column's existence) before converting anything, so a
        # bad target type or a missing column is a clear config error rather than a KeyError
        # or an unsupported-type ValueError from deep inside the conversion.
        self.infer_output_schema(input_df.schema, config)
        df = input_df.df.copy()
        series = df[column]

        if target_type == "NUMBER":
            df[column] = pd.to_numeric(series, errors="coerce")
        elif target_type == "STRING":
            df[column] = series.astype(str).where(series.notna(), None)
        elif target_type == "DATE":
            df[column] = _to_datetime_coercing(series)
        else:
            raise ValueError(f"Unsupported target type '{target_type}'.")

        new_schema = self.infer_output_schema(input_df.schema, config)
        return FluxDataFrame(schema=new_schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        column_ref = f"[{config.get('column') or '?'}]"
        target_type = config.get("target_type")
        if target_type == "NUMBER":
            return f"VALUE({column_ref})"
        if target_type == "STRING":
            return f'TEXT({column_ref}, "@")'
        if target_type == "DATE":
            return f"DATEVALUE({column_ref})"
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        column = config.get("column", "?")
        target_type = config.get("target_type", "?")
        return f"Convert {column} to {target_type}. Values that can't convert become blank."

    def compute_row_errors(
        self, input_df: FluxDataFrame, output_df: FluxDataFrame, config: dict
    ) -> Optional[list[int]]:
        column = config.get("column")
        if not column or column not in input_df.df.columns or column not in output_df.df.columns:
            return None
        was_null = input_df.df[column].isna()
        is_null = output_df.df[column].isna()
        newly_null = (~was_null) & is_null
        indices = output_df.df.index[newly_null].tolist()
        return indices or None
