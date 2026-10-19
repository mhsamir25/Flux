from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import DataSchema


class NodeCategory(str, Enum):
    SOURCE = "SOURCE"
    TRANSFORM = "TRANSFORM"
    AGGREGATE = "AGGREGATE"
    JOIN = "JOIN"
    OUTPUT = "OUTPUT"


class FieldType(str, Enum):
    COLUMN_SELECT = "COLUMN_SELECT"
    MULTI_COLUMN_SELECT = "MULTI_COLUMN_SELECT"
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    ENUM = "ENUM"              # dropdown; used for operators, join types, agg functions, etc.
    TOGGLE = "TOGGLE"
    COLOR_PICKER = "COLOR_PICKER"
    EXPRESSION = "EXPRESSION"  # structured operand/operator/operand, used by add_calculated_column


class FieldSchema(BaseModel):
    key: str
    label: str
    type: FieldType
    placeholder: Optional[str] = None
    required: bool = True
    options: Optional[list[str]] = None   # populated for ENUM fields


class SchemaValidationError(Exception):
    """Raised with a plain-English message when inferred output schema is invalid."""


class NodePlugin(ABC):
    id: str                    # unique machine id, e.g. "filter", "group_by_aggregate"
    display_name: str
    category: NodeCategory
    input_ports: int = 1       # 0 for source nodes, 2 for join
    output_ports: int = 1

    formula_exportable: bool = True

    @abstractmethod
    def get_config_schema(self) -> list[FieldSchema]:
        ...

    @abstractmethod
    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        """Compute output schema WITHOUT executing. Raise SchemaValidationError on invalid config."""
        ...

    @abstractmethod
    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        """Single-input nodes override this."""
        ...

    def execute_join(self, left: FluxDataFrame, right: FluxDataFrame, config: dict) -> FluxDataFrame:
        """Only join_node overrides this. Default raises NotImplementedError."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support execute_join()")

    def execute_source(self, config: dict) -> FluxDataFrame:
        """Only source nodes override this."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support execute_source()")

    def requires_reparse(self, config: dict) -> bool:
        """Whether this source node's config asks for something the cached parse can't give.

        Default False: a source whose output is fully determined by its config needs no
        re-parse, and every source whose data came inline (raw CSV text) is unaffected.
        """
        return False

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        """Return None if this node has no Excel equivalent (e.g. rename_column, limit_rows, pivot)."""
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        """Plain-English explanation of what this step does, for the Explain feature."""
        return ""

    def compute_row_errors(
        self, input_df: FluxDataFrame, output_df: FluxDataFrame, config: dict
    ) -> Optional[list[int]]:
        return None
