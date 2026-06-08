"""
Contract for NodePlugin system.

This module defines the abstract base class for all pipeline nodes,
the configuration field schema, and a central registry for node types.

All node implementations (filter, sort, join, etc.) must subclass NodePlugin
and implement the required abstract methods. They are then registered with
NodeRegistry to be discoverable by the FastAPI execution engine.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from pydantic import BaseModel
from models.data_frame import DataFrame
from models.data_schema import DataSchema

class FieldSchema(BaseModel):
    """
    Describes a single config field for a node. Frontend uses this to render UI.
    Describes what a config file should look like. For example: If a Filter Node needs to know
    which column to filter and what value to look for, it uses FieldSchema to tell the frontend,
    render a dropdown menu for columns and a text box for value
    """
    key: str                       # Name of the field (e.g., "column", "operator")
    label: str                     # Human-readable label (e.g., "Select Column")
    type: str                      # COLUMN_SELECT, MULTI_COLUMN_SELECT, TEXT, NUMBER, OPERATOR_SELECT, TOGGLE
    placeholder: str = ""          # The faint hint text that appears inside an empty field before the user starts typing
    required: bool = True          # A flag stating wheather this input field is mandatory or optional
    options: List[str] = []        # A list of predefined choices, this field is exclusively used when the 
                                   # the type is set to something that requires a list of choices(like a dropdown menu)

class NodePlugin(ABC):

    @abstractmethod
    def get_id(self) -> str:
        """Unique machine-readable ID, e.g. 'filter'."""
        ...

    @abstractmethod
    def get_display_name(self) -> str:
        """Human-readable label for UI sidebar."""
        ...

    @abstractmethod
    def get_category(self) -> str:
        """One of: SOURCE, TRANSFORM, AGGREGATE, JOIN, OUTPUT."""
        ...

    @abstractmethod
    def get_config_schema(self) -> List[FieldSchema]:
        """List of FieldSchema for dynamic config panel."""
        ...

    @abstractmethod
    def infer_output_schema(self, input_schema: Optional[DataSchema], config: dict) -> DataSchema:
        """
        Return output schema without execution. Raise if invalid.
        Predicts what the data will look like after running the node without processing the rows
        For example: If a node removes a column, it calculates the new schema instantly so the 
        frontend UI can update immediately. 
        """
        ...

    def execute(self, input_df: DataFrame, config: dict) -> DataFrame:
        """Transform/aggregate/output node execution."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    def execute_source(self, csv_data: str, config: dict) -> DataFrame:
        """Source node execution (read CSV)."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute_source()")

    def execute_join(self, left: DataFrame, right: DataFrame, config: dict) -> DataFrame:
        """Join node execution (inner/left/right/full)."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute_join()")

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        """Return Excel formula equivalent, or None."""
        return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        """Plain-English explanation of this step."""
        return ""


class NodeRegistry:
    _plugins: dict = {}

    @classmethod
    def register(cls, plugin: NodePlugin):
        cls._plugins[plugin.get_id()] = plugin

    @classmethod
    def get(cls, node_id: str) -> NodePlugin:
        if node_id not in cls._plugins:
            raise KeyError(f"Node type '{node_id}' is not registered.")
        return cls._plugins[node_id]

    @classmethod
    def get_all(cls) -> List[NodePlugin]:
        return list(cls._plugins.values())
    
    