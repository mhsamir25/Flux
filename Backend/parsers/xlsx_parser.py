import openpyxl
import io
import base64
from models.data_frame import DataFrame
from models.data_schema import DataSchema
from models.column import Column
from models.data_type import DataType

def parse_xlsx(xlsx_bytes_or_b64: str | bytes) -> DataFrame:
    if isinstance(xlsx_bytes_or_b64, str):
        if "," in xlsx_bytes_or_b64:
            xlsx_bytes_or_b64 = xlsx_bytes_or_b64.split(",")[1]
        xlsx_bytes = base64.b64decode(xlsx_bytes_or_b64)
    else:
        xlsx_bytes = xlsx_bytes_or_b64

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    sheet = wb.active

    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        return DataFrame(schema=DataSchema(columns=[]), rows=[], total_row_count=0)

    header = [str(h) if h is not None else f"Column_{i}" for i, h in enumerate(header)]

    data_rows = []
    for row in rows_iter:
        data_rows.append(dict(zip(header, row)))

    columns = []
    for col_name in header:
        columns.append(Column(name=col_name, type=DataType.ANY, nullable=True))

    schema = DataSchema(columns=columns)
    return DataFrame(schema=schema, rows=data_rows, total_row_count=len(data_rows))
