from typing import List, Dict, Any
from .data_schema import DataSchema
from .data_type import DataType

class DataFrame:
    def __init__(self, schema: DataSchema, rows: List[Dict[str, Any]], total_row_count: int):
        self.schema=schema
        self.rows=rows
        self.total_row_count=total_row_count
    
    def preview(self, max_rows:int=20)->"DataFrame":
        return DataFrame(
            schema=self.schema,
            rows=self.rows[:max_rows],
            total_row_count=self.total_row_count,
        )
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
        
    def to_preview_dict(self, max_rows: int=20)->Dict:
        preview=self.preview(max_rows)
        return{
            "columns": [{"name": c.name, "type": c.type} for c in preview.schema.columns],
            "rows": preview.rows,
        }
    
    """
    The Actual Data in each of the columns, the data container
    We are using plain python class for DataFrame instead of Pydantic because
    pydantic is only great for small, structured data like config, API requests
    but dataframe holds potentially thousands of rows
    """