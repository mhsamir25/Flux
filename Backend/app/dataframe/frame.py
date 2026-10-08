"""
FluxDataFrame: the internal data representation every node plugin operates on and returns.
"""

import json
from dataclasses import dataclass

import pandas as pd

from .schema import Column, DataSchema, DataType


@dataclass(eq=False)  # a pandas DataFrame has no well-defined truth value under ==
class FluxDataFrame:
    schema: DataSchema
    df: pd.DataFrame
    total_row_count: int

    def preview(self, max_rows: int = 100) -> "FluxDataFrame":
        """Returns a copy with only the first max_rows rows; total_row_count unchanged."""
        return FluxDataFrame(
            schema=self.schema,
            df=self.df.head(max_rows).reset_index(drop=True),
            total_row_count=self.total_row_count,
        )

    def with_schema(self, schema: DataSchema) -> "FluxDataFrame":
        return FluxDataFrame(schema=schema, df=self.df, total_row_count=self.total_row_count)

    def add_column(self, name: str, dtype: DataType, values: pd.Series) -> "FluxDataFrame":
        new_df = self.df.copy()
        new_df[name] = values
        new_schema = DataSchema(columns=[*self.schema.columns, Column(name=name, type=dtype)])
        return FluxDataFrame(schema=new_schema, df=new_df, total_row_count=self.total_row_count)

    def to_json_records(self) -> list[dict]:
        """Row-oriented JSON-safe records (NaN -> null, numpy scalars -> native types)."""
        if self.df.empty:
            return []
        return json.loads(self.df.to_json(orient="records", date_format="iso"))
