from enum import Enum

class DataType(str, Enum):
    NUMBER = "NUMBER"
    STRING = "STRING"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    ANY = "ANY"

    """
    Multiple Inheritance, by inheriting from str, each enum
    member is behaving like a String, useful for JSON 
    Serialization

    Reason: FastAPI and Pydantic automatically converts 
    enums to Strings in API responses. The str inheritance 
    makes it useful
    """

