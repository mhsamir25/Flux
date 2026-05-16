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
    data models with automatic validation

    Nullable is set to true because a column can have 
    some rows with missing values
    """
