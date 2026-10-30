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

    # Added in Phase 10 for GET /api/nodes' NodeCatalogueEntry.formula_exportable (§8.1).
    # The plan suggests computing this dynamically as "to_excel_formula(None, {}) is not
    # None", but that check gives wrong answers for real nodes: data_table's to_excel_formula
    # is an identity passthrough of input_ref, so calling it with input_ref=None returns None
    # even though data_table never itself breaks a formula chain; add_calculated_column
    # returns None for an empty/unconfigured expression even though it's normally exportable
    # once configured. A fixed per-node-TYPE declaration sidesteps both false negatives —
    # override to False only on nodes that structurally NEVER have an Excel equivalent
    # regardless of config (pivot, rename_column, limit_rows, the three chart nodes).
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

        Source data reaches a pipeline as an already-parsed FluxDataFrame from the
        data_reference_id cache (§11), but for some sources the *config* decides part of what
        gets parsed — read_xlsx's sheet_name picks which sheet to read, and that choice can
        only be honoured by parsing the original bytes again. This hook is how a source node
        says "my config needs the raw upload, not the cached frame", so the executor can
        re-parse instead of silently returning a frame parsed with different settings.

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
        """Optional hook (added in Phase 6, not part of the original §5 spec): row indices
        that individually failed within an otherwise *successful* execution — e.g.
        convert_type's coerce-to-null behavior — for NodeResult.error_row_indices row-level
        UI highlighting (§7.1) without the whole node being marked as failed. The executor
        calls this generically on every single-input node after a successful execute(), so
        adding row-level reporting to a new node later never requires touching the executor.
        Default: no row-level errors to report.
        """
        return None
