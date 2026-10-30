from typing import Optional

import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError

_JOIN_TYPE_MAP = {"INNER": "inner", "LEFT": "left", "RIGHT": "right", "FULL": "outer"}


class JoinNode(NodePlugin):
    id = "join"
    display_name = "Join"
    category = NodeCategory.JOIN
    input_ports = 2
    output_ports = 1

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="left_key", label="Left Key Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="right_key", label="Right Key Column", type=FieldType.COLUMN_SELECT),
            FieldSchema(key="join_type", label="Join Type", type=FieldType.ENUM,
                        options=list(_JOIN_TYPE_MAP.keys())),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        right_schema = config.get("_right_schema")
        if right_schema is None:
            raise SchemaValidationError("Join requires both a left and a right input to be connected.")
        left_key, right_key = config.get("left_key"), config.get("right_key")
        if not left_key or not input_schema.has_column(left_key):
            raise SchemaValidationError(f"Column '{left_key}' not found in the left input.")
        if not right_key or not right_schema.has_column(right_key):
            raise SchemaValidationError(f"Column '{right_key}' not found in the right input.")
        join_type = config.get("join_type")
        if join_type not in _JOIN_TYPE_MAP:
            raise SchemaValidationError(f"Unsupported join type '{join_type}'.")
        return _merged_schema(input_schema, right_schema, left_key, right_key)

    def execute(self, input_df, config):
        raise NotImplementedError("join is a join node; use execute_join() instead")

    def execute_join(self, left: FluxDataFrame, right: FluxDataFrame, config: dict) -> FluxDataFrame:
        left_key, right_key = config.get("left_key"), config.get("right_key")
        join_type = config.get("join_type")
        pandas_how = _JOIN_TYPE_MAP.get(join_type)
        if pandas_how is None:
            raise ValueError(f"Unsupported join type '{join_type}'.")
        if left_key not in left.df.columns:
            raise ValueError(f"Column '{left_key}' not found in the left input.")
        if right_key not in right.df.columns:
            raise ValueError(f"Column '{right_key}' not found in the right input.")

        merged = pd.merge(
            left.df, right.df, left_on=left_key, right_on=right_key,
            how=pandas_how, suffixes=("_left", "_right"),
        )
        schema = _merged_schema(left.schema, right.schema, left_key, right_key)
        return FluxDataFrame(schema=schema, df=merged, total_row_count=len(merged))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        join_type = config.get("join_type")
        if join_type not in ("LEFT", "INNER"):
            return None  # XLOOKUP is inherently a left-lookup; no clean RIGHT/FULL equivalent
        left_key = config.get("left_key") or "?"
        right_key = config.get("right_key") or "?"
        return f"XLOOKUP([{left_key}], [Right!{right_key}], [Right!*])"

    def to_excel_formula_explanation(self, config: dict) -> str:
        join_type = config.get("join_type", "?")
        left_key = config.get("left_key", "?")
        right_key = config.get("right_key", "?")
        if join_type not in ("LEFT", "INNER"):
            return (
                f"{join_type} join on {left_key} = {right_key}. "
                "No Excel formula equivalent — XLOOKUP only supports left-style lookups."
            )
        return (
            f"For each row, look up {right_key} in the right table where it matches {left_key}, "
            "returning the matching columns from the right table."
        )


def _merged_schema(left_schema: DataSchema, right_schema: DataSchema, left_key: str, right_key: str) -> DataSchema:
    left_names, right_names = set(left_schema.column_names()), set(right_schema.column_names())
    same_key = left_key == right_key
    overlap = (left_names & right_names) - ({left_key} if same_key else set())

    columns = []
    for col in left_schema.columns:
        if same_key and col.name == left_key:
            columns.append(Column(name=col.name, type=col.type, nullable=True))
            continue
        name = f"{col.name}_left" if col.name in overlap else col.name
        columns.append(Column(name=name, type=col.type, nullable=True))
    for col in right_schema.columns:
        if same_key and col.name == right_key:
            continue  # already added once from the left side
        name = f"{col.name}_right" if col.name in overlap else col.name
        columns.append(Column(name=name, type=col.type, nullable=True))
    return DataSchema(columns=columns)
