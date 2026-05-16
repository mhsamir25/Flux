#Describes the structure of the data(Columns, types)

from pydantic import BaseModel
from typing import List, Optional
from .column import Column

class DataSchema(BaseModel):
    columns: List[Column]

    def has_column(self, name: str)->bool:
        return any(c.name==name for c in self.columns)
        """
        Checks if a column exists
        """
    
    def get_column(self, name:str) -> Optional[Column]:
        for c in self.columns:
            if c.name==name:
                return c
            raise KeyError(f"Column '{name}' not found in Schema")
        """
        get the column metadata
        """

    def column_names(self)->List[str]:
        return [c.name for c in self.columns]
        """
        returns just the names as a list
        """    
