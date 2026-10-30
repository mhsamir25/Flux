from pydantic import BaseModel

from app.dataframe.schema import Column


class DataUploadResponse(BaseModel):
    data_reference_id: str
    columns: list[Column]
    row_count: int
