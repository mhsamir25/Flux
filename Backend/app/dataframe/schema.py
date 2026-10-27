"""Canonical schema types shared by every node plugin, the executor, and the API layer."""
from enum import Enum
from typing import List

from pydantic import BaseModel


class DataType(str, Enum):
    NUMBER = "NUMBER"
    STRING = "STRING"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    ANY = "ANY"


class Column(BaseModel):
    name: str
    type: DataType
    nullable: bool = True


class DataSchema(BaseModel):
    columns: List[Column]

    def has_column(self, name: str) -> bool:
        return any(c.name == name for c in self.columns)

    def get_column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(f"Column '{name}' not found in schema")

    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]
