from typing import Optional

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class RenameColumnNode(NodePlugin):
    id = "rename_column"
    display_name = "Rename Column"
    category = NodeCategory.TRANSFORM
    formula_exportable = False

    def get_config_schema(self) -> list[FieldSchema]:
        return [FieldSchema(key="mappings", label="Column Renames", type=FieldType.TEXT, required=False)]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        rename_map = _build_rename_map(input_schema, config)
        columns = []
        seen_names = set()
        for col in input_schema.columns:
            new_name = rename_map.get(col.name, col.name)
            if new_name in seen_names:
                raise SchemaValidationError(f"Duplicate output column name '{new_name}' after renaming.")
            seen_names.add(new_name)
            columns.append(Column(name=new_name, type=col.type, nullable=col.nullable))
        return DataSchema(columns=columns)

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        rename_map = {p["from"]: p["to"] for p in (config.get("mappings") or []) if p.get("from") and p.get("to")}
        df = input_df.df.rename(columns=rename_map)
        new_schema = self.infer_output_schema(input_df.schema, config)
        return FluxDataFrame(schema=new_schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        return None  # Excel doesn't rename ranges via formula

    def to_excel_formula_explanation(self, config: dict) -> str:
        mappings = config.get("mappings") or []
        if not mappings:
            return "Rename columns."
        described = ", ".join(f"{p.get('from')} → {p.get('to')}" for p in mappings)
        return f"Rename columns: {described}. (No Excel formula equivalent — renaming isn't expressible as a formula.)"


def _build_rename_map(input_schema: DataSchema, config: dict) -> dict:
    mappings = config.get("mappings") or []
    rename_map = {}
    for pair in mappings:
        src, dst = pair.get("from"), pair.get("to")
        if not src or not dst:
            raise SchemaValidationError("Each rename mapping needs both a source and target column name.")
        if not input_schema.has_column(src):
            raise SchemaValidationError(f"Column '{src}' not found in the input data.")
        rename_map[src] = dst
    return rename_map
