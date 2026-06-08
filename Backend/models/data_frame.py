from typing import List, Dict, Any
from .data_schema import DataSchema
from .data_type import DataType

class DataFrame:
    def __init__(self, schema: DataSchema, rows: List[Dict[str, Any]], total_row_count: int):
        self.schema=schema
        self.rows=rows
        self.total_row_count=total_row_count
        """
        rows: List[Dict[str, Any]]---How the data is stored in the memory,
        expects a list of dictionaries. Each dict represents a single row,
        where the key(str) is a column name and the value(Any) is the data 
        in the cell
        """
    
    def preview(self, max_rows:int=20)->"DataFrame":
        return DataFrame(
            schema=self.schema,
            rows=self.rows[:max_rows],
            total_row_count=self.total_row_count,
        )
        """
        Syntax: uses quotes alongside Dataframe because it is still being 
        defined. This tells python "I am going to return an instance of myself"

        Creates and returns a brand new DataFrame Object, uses slicing to only 
        copy the first 20 rows. Prevents from accidentally printing millions of 
        rows on our screen
        """
    def add_column(self, name: str, dtype:DataType, values: List[Any])->"DataFrame":
        from .column import Column
        new_schema = DataSchema(
            columns=list(self.schema.columns)+[Column(name=name,type=dtype)]
        )
        new_rows=[]

        for i, row in enumerate(self.rows):
            new_row=dict(row)
            new_row[name]=values[i] if i<len(values) else None
            new_rows.append(new_row)
    
        return DataFrame(schema=new_schema, rows=new_rows, total_row_count=self.total_row_count)
        """
        the column is imported inside the method to prevent circular imports
        in python, so it doesnt crash

        enumerate is used to loop through the existing rows and add the new column 
        value to each row. If there are more rows than values provided, 
        it fills in None for those extra rows.
        """
    def to_preview_dict(self, max_rows: int=20)->Dict:
        preview=self.preview(max_rows)
        return{
            "columns": [{"name": c.name, "type": c.type} for c in preview.schema.columns],
            "rows": preview.rows,
        }
    
        """
        It is taking the python objects(DataFrame, DataSchema, Column) and is flattening them
        up into a standard python Dict made up of basic types like strings, lists
        and numbers
        Crucial because FastAPI or React cannot understand our custom DataFrame class, they 
        need standard JSON data
        """
    
    """
    The Actual Data in each of the columns, the data container
    We are using plain python class for DataFrame instead of Pydantic because
    pydantic is only great for small, structured data like config, API requests
    but dataframe holds potentially thousands of rows

    This is like the simplified, custom version of a Pandas dataframe

    Purpose: Hold the data structure(schema) alongside the actual 
    records(rows)
    Provide a way to cut down massive datasets into smaller chunks for 
    quick reviewing(preview)
    Allow us to dynamically modify our dataset by appending new columns(add_column)
    Format the data cleanly into standard Python dictionaries so it can easily be 
    sent over an API or converted into JSON(to_preview_dict)
    """