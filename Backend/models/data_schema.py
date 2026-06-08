#Describes the structure of the data(Columns, types)

from pydantic import BaseModel
from typing import List, Optional
# List: Specifies a collection of items
# Optional: A value could be either be a specific type or None
from .column import Column

class DataSchema(BaseModel):
    columns: List[Column]
    # The dataschema object must contain a column field
    # which is basically a list of Column Datatype
    def has_column(self, name: str)->bool:
        return any(c.name==name for c in self.columns)
        """
        Checks if a column exists
        any function returns true if at least one item in the 
        iterable is True.
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
    """
    The Column class defines a single column, DataSchema acts as a container for a 
    collection of columns and provides built-in helper methods 
    to search and manage them.

    Purpose: Grouping multiple column objects together into a single list and
    give us an easy way to interact with them. Instead of manually looping through
    lists in our main application code, this class lets us ask questions like:

    1) Does this dataset have a column named 'email'?
    2) Give me all the metadata for the 'user_id' column
    3) Give me a clean list of just the column names
    """
