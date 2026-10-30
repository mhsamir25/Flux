from typing import Optional

import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError

_OPERATORS = ["=", "≠", ">", "<", "≥", "≤", "contains", "starts_with", "is_empty", "is_not_empty"]
_EXCEL_OPERATOR_MAP = {"=": "=", "≠": "<>", ">": ">", "<": "<", "≥": ">=", "≤": "<="}


class FilterNode(NodePlugin):
    id = "filter"
    display_name = "Filter"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="operator", label="Operator", type=FieldType.ENUM, options=_OPERATORS),
            FieldSchema(key="value", label="Value", type=FieldType.TEXT, required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        _require_column(input_schema, config.get("column"))
        second_column = config.get("column2")
        if second_column:
            _require_column(input_schema, second_column)
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        df = input_df.df
        mask = _build_condition_mask(df, config.get("column"), config.get("operator"), config.get("value"))

        second_column = config.get("column2")
        if second_column:
            second_mask = _build_condition_mask(
                df, second_column, config.get("operator2"), config.get("value2")
            )
            logic = (config.get("logic") or "AND").upper()
            mask = (mask & second_mask) if logic == "AND" else (mask | second_mask)

        filtered = df[mask].reset_index(drop=True)
        return FluxDataFrame(schema=input_df.schema, df=filtered, total_row_count=len(filtered))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        condition = _excel_condition(config.get("column"), config.get("operator"), config.get("value"))
        return f"FILTER({input_ref}, {condition})"

    def to_excel_formula_explanation(self, config: dict) -> str:
        column = config.get("column", "?")
        operator = config.get("operator", "?")
        value = config.get("value", "")
        return f"Keep only rows where {column} {operator} {value}.".rstrip()


def _require_column(schema: DataSchema, column: Optional[str]) -> None:
    if not column:
        raise SchemaValidationError("Filter requires a column to be selected.")
    if not schema.has_column(column):
        raise SchemaValidationError(f"Column '{column}' not found in the input data.")


def _build_condition_mask(df: pd.DataFrame, column: Optional[str], operator: Optional[str], value) -> pd.Series:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in the input data.")
    series = df[column]

    if operator == "is_empty":
        return series.isna() | (series.astype(str).str.strip() == "")
    if operator == "is_not_empty":
        return ~(series.isna() | (series.astype(str).str.strip() == ""))
    if operator == "contains":
        return series.astype(str).str.contains(str(value), na=False)
    if operator == "starts_with":
        return series.astype(str).str.startswith(str(value), na=False)

    comparable = _cast_value_for_comparison(series, value)
    if operator == "=":
        return series == comparable
    if operator == "≠":
        return series != comparable
    if operator == ">":
        return series > comparable
    if operator == "<":
        return series < comparable
    if operator == "≥":
        return series >= comparable
    if operator == "≤":
        return series <= comparable
    raise ValueError(f"Unsupported filter operator '{operator}'.")


def _cast_value_for_comparison(series: pd.Series, value):
    if pd.api.types.is_numeric_dtype(series):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"'{value}' is not a valid number to compare against column values.")
    if pd.api.types.is_datetime64_any_dtype(series):
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            raise ValueError(f"'{value}' is not a valid date to compare against column values.")
        return parsed
    return value


def _excel_condition(column: Optional[str], operator: Optional[str], value) -> str:
    column_ref = f"[{column}]" if column else "[?]"
    if operator == "is_empty":
        return f'{column_ref}=""'
    if operator == "is_not_empty":
        return f'{column_ref}<>""'
    if operator == "contains":
        return f'ISNUMBER(SEARCH("{value}",{column_ref}))'
    if operator == "starts_with":
        return f'LEFT({column_ref},LEN("{value}"))="{value}"'
    excel_op = _EXCEL_OPERATOR_MAP.get(operator, operator or "=")
    value_literal = value if _looks_numeric(value) else f'"{value}"'
    return f"{column_ref}{excel_op}{value_literal}"


def _looks_numeric(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
