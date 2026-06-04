import csv
import io
from datetime import datetime
from typing import List, Dict, Any
from models.data_type import DataType
from models.column import Column
from models.data_schema import DataSchema
from models.data_frame import DataFrame


def _infer_type(value: str) -> DataType:
    if value is None or value.strip() == "":
        return DataType.STRING
    try:
        float(value)
        return DataType.NUMBER
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            datetime.strptime(value.strip(), fmt)
            return DataType.DATE
        except ValueError:
            pass
    return DataType.STRING


def _coerce_value(value: str, dtype: DataType) -> Any:
    if value is None or value.strip() == "":
        return None
    if dtype == DataType.NUMBER:
        try:
            v = float(value)
            return int(v) if v == int(v) else v
        except ValueError:
            return None
    if dtype == DataType.DATE:
        return value.strip()
    return value


def parse_csv(csv_data: str) -> DataFrame:
    reader = csv.DictReader(io.StringIO(csv_data))
    raw_rows: List[Dict[str, str]] = []
    for row in reader:
        raw_rows.append(dict(row))

    if not raw_rows:
        return DataFrame(schema=DataSchema(columns=[]), rows=[], total_row_count=0)

    headers = list(raw_rows[0].keys())

    # Infer types from first 20 rows
    sample = raw_rows[:20]
    col_types: Dict[str, DataType] = {}
    for header in headers:
        types = [_infer_type(r.get(header, "")) for r in sample]
        # Pick most common non-STRING type, or STRING if all strings
        if all(t == DataType.NUMBER for t in types):
            col_types[header] = DataType.NUMBER
        elif all(t == DataType.DATE for t in types):
            col_types[header] = DataType.DATE
        else:
            col_types[header] = DataType.STRING

    columns = [Column(name=h, type=col_types[h]) for h in headers]
    schema = DataSchema(columns=columns)

    rows = []
    for raw in raw_rows:
        row = {}
        for h in headers:
            row[h] = _coerce_value(raw.get(h, ""), col_types[h])
        rows.append(row)

    return DataFrame(schema=schema, rows=rows, total_row_count=len(rows))
