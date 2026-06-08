from pydantic import BaseModel   
from .data_type import DataType

class Column(BaseModel):
    name:str
    type:DataType
    nullable: bool = True
    """
    Pydantic: Library for validating data and 
    converting it to python object
    BaseModel: The Parent Class for creating 
    data models with automatic validation(type checking,
    data validation, easy conversion to JSON)

    Nullable is set to true because a column can have 
    some rows with missing values

    Purpose: Create a structured, validated data model called Column.
    If we try to create a column but forget it to give a name, or if we 
    provide the wrong datatype, python will throw an error.
    """
