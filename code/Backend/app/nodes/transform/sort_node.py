from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class SortNode(NodePlugin):
    id = "sort"
    display_name = "Sort"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="column", label="Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="direction", label="Direction", type=FieldType.TOGGLE,
                        options=["ASC", "DESC"], required=False),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        keys = _sort_keys(config)
        if not keys:
            raise SchemaValidationError("Sort requires at least one column.")
        for key in keys:
            if not input_schema.has_column(key["column"]):
                raise SchemaValidationError(f"Column '{key['column']}' not found in the input data.")
        return input_schema

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        keys = _sort_keys(config)
        if not keys:
            raise ValueError("Sort requires at least one column.")
        columns = [k["column"] for k in keys]
        ascending = [k["direction"].upper() != "DESC" for k in keys]
        sorted_df = input_df.df.sort_values(by=columns, ascending=ascending).reset_index(drop=True)
        return FluxDataFrame(schema=input_df.schema, df=sorted_df, total_row_count=len(sorted_df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        keys = _sort_keys(config)
        if not keys:
            return None
        primary = keys[0]
        order = -1 if primary["direction"].upper() == "DESC" else 1
        return f"SORT({input_ref}, [{primary['column']}], {order})"

    def to_excel_formula_explanation(self, config: dict) -> str:
        keys = _sort_keys(config)
        if not keys:
            return "Sort rows."
        primary = keys[0]
        note = f"Sort rows by {primary['column']} ({primary['direction'].upper()})."
        if len(keys) > 1:
            extra = ", ".join(f"{k['column']} ({k['direction'].upper()})" for k in keys[1:])
            note += (
                f" Additional sort keys — {extra} — aren't reflected in the exported Excel "
                "formula; this generator only exports the primary sort key."
            )
        return note


def _sort_keys(config: dict) -> list[dict]:
    if config.get("sort_keys"):
        return [
            {"column": k["column"], "direction": (k.get("direction") or "ASC")}
            for k in config["sort_keys"]
        ]
    column = config.get("column")
    if not column:
        return []
    return [{"column": column, "direction": config.get("direction") or "ASC"}]
