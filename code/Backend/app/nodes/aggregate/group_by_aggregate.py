"""AGGREGATE node: group_by_aggregate 

`config["aggregations"]` is a list of {"column": ..., "function": ...} dicts — structurally a
list, same convention as rename_column's `mappings` (§13: frontend renders a dedicated
sub-form for it). AGGREGATE_FUNCTIONS / PANDAS_FUNC_MAP are exported so pivot.py can reuse the
same aggregation-function vocabulary rather than duplicating it — pivot_table's aggfunc needs
the identical SUM/AVERAGE/COUNT/MIN/MAX/COUNT_DISTINCT set.

Excel export only renders the *first* aggregation's formula (same documented limitation as
sort's multi-key case) — a grouped table with several aggregation columns doesn't collapse
into one Excel formula, since each output column would need its own SUMIF/AVERAGEIF/etc.
COUNT_DISTINCT has no single-formula Excel equivalent at all (would need a SUMPRODUCT/COUNTIF
trick), so it's skipped even as the "first aggregation" case.
"""
from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError

AGGREGATE_FUNCTIONS = ["SUM", "AVERAGE", "COUNT", "MIN", "MAX", "COUNT_DISTINCT"]
PANDAS_FUNC_MAP = {
    "SUM": "sum", "AVERAGE": "mean", "COUNT": "size",
    "MIN": "min", "MAX": "max", "COUNT_DISTINCT": "nunique",
}
_EXCEL_IFS_FUNCS = {"MIN": "MINIFS", "MAX": "MAXIFS"}


class GroupByAggregateNode(NodePlugin):
    id = "group_by_aggregate"
    display_name = "Group By Aggregate"
    category = NodeCategory.AGGREGATE

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="group_column", label="Group By Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="aggregations", label="Aggregations", type=FieldType.TEXT, required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        group_column = config.get("group_column")
        if not group_column:
            raise SchemaValidationError("Group By Aggregate requires a group column.")
        if not input_schema.has_column(group_column):
            raise SchemaValidationError(f"Column '{group_column}' not found in the input data.")
        aggregations = config.get("aggregations") or []
        if not aggregations:
            raise SchemaValidationError("Group By Aggregate requires at least one aggregation.")

        columns = [input_schema.get_column(group_column)]
        seen_names = {group_column}
        for agg in aggregations:
            col, func = agg.get("column"), agg.get("function")
            if not col:
                raise SchemaValidationError("Each aggregation requires a column to aggregate.")
            if not input_schema.has_column(col):
                raise SchemaValidationError(f"Column '{col}' not found in the input data.")
            if func not in AGGREGATE_FUNCTIONS:
                raise SchemaValidationError(f"Unsupported aggregation function '{func}'.")
            output_name = _output_column_name(col, func)
            if output_name in seen_names:
                raise SchemaValidationError(
                    f"Duplicate output column name '{output_name}' — each column/function pair must be unique."
                )
            seen_names.add(output_name)
            result_type = input_schema.get_column(col).type if func in ("MIN", "MAX") else DataType.NUMBER
            columns.append(Column(name=output_name, type=result_type, nullable=True))
        return DataSchema(columns=columns)

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        group_column = config.get("group_column")
        aggregations = config.get("aggregations") or []
        if not group_column:
            raise ValueError("Group By Aggregate requires a group column.")
        if not aggregations:
            raise ValueError("Group By Aggregate requires at least one aggregation.")

        df = input_df.df
        named_aggs = {}
        for agg in aggregations:
            col, func = agg.get("column"), agg.get("function")
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in the input data.")
            pandas_func = PANDAS_FUNC_MAP.get(func)
            if pandas_func is None:
                raise ValueError(f"Unsupported aggregation function '{func}'.")
            named_aggs[_output_column_name(col, func)] = (col, pandas_func)

        grouped = df.groupby(group_column, as_index=False, dropna=False).agg(**named_aggs)
        new_schema = self.infer_output_schema(input_df.schema, config)
        return FluxDataFrame(schema=new_schema, df=grouped, total_row_count=len(grouped))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        group_column = config.get("group_column")
        aggregations = config.get("aggregations") or []
        if not group_column or not aggregations:
            return None

        first = aggregations[0]
        func, value_col = first.get("function"), first.get("column")
        group_ref = f"[{group_column}]"
        value_ref = f"[{value_col}]"
        unique_groups = f"UNIQUE({group_ref})"

        if func == "COUNT":
            return f"COUNTIF({group_ref}, {unique_groups})"
        if func in ("MIN", "MAX"):
            return f"{_EXCEL_IFS_FUNCS[func]}({value_ref}, {group_ref}, {unique_groups})"
        if func == "SUM":
            return f"SUMIF({group_ref}, {unique_groups}, {value_ref})"
        if func == "AVERAGE":
            return f"AVERAGEIF({group_ref}, {unique_groups}, {value_ref})"
        return None  # COUNT_DISTINCT has no clean single-formula Excel equivalent

    def to_excel_formula_explanation(self, config: dict) -> str:
        group_column = config.get("group_column", "?")
        aggregations = config.get("aggregations") or []
        if not aggregations:
            return f"Group rows by {group_column}."
        first = aggregations[0]
        note = f"Group rows by {group_column}, computing {first.get('function')}({first.get('column')}) per group."
        if first.get("function") == "COUNT_DISTINCT":
            note += " COUNT_DISTINCT has no single-formula Excel equivalent, so no formula is exported."
        if len(aggregations) > 1:
            extra = ", ".join(f"{a.get('function')}({a.get('column')})" for a in aggregations[1:])
            note += (
                f" Additional aggregations — {extra} — aren't reflected in the exported formula; "
                "each would need its own formula column in Excel."
            )
        return note


def _output_column_name(column: str, function: str) -> str:
    return f"{column}_{function.lower()}"
