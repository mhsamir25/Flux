import csv
import io
from typing import Optional, Union

import pandas as pd
from charset_normalizer import from_bytes

from app.dataframe.frame import FluxDataFrame
from app.dataframe.inference import infer_column_type
from app.dataframe.schema import Column, DataSchema, DataType

MAX_ROWS = 50_000
_SNIFF_SAMPLE_SIZE = 8192
_DELIMITER_CANDIDATES = ",;\t|"
_INJECTION_PREFIXES = ("=", "+", "-", "@")


class FileParsingError(Exception):
    """Raised with a plain-English message when a CSV/XLSX file can't be parsed."""


def detect_encoding(raw: bytes) -> str:
    """Try UTF-8 first, fall back to charset-normalizer detection."""
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    best = from_bytes(raw).best()
    if best is not None and best.encoding:
        return best.encoding
    return "latin-1"  

def sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=_DELIMITER_CANDIDATES)
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_csv(data: Union[str, bytes], max_rows: int = MAX_ROWS) -> FluxDataFrame:
    """Parse raw CSV content (already-decoded str, or raw upload bytes) into a FluxDataFrame."""
    if isinstance(data, bytes):
        text = data.decode(detect_encoding(data), errors="replace")
    else:
        text = data

    text = text.lstrip("﻿") 

    if text.strip() == "":
        return FluxDataFrame(schema=DataSchema(columns=[]), df=pd.DataFrame(), total_row_count=0)

    delimiter = sniff_delimiter(text[:_SNIFF_SAMPLE_SIZE])

    try:
        raw_df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            engine="python",
        )
    except (pd.errors.ParserError, csv.Error) as e:
        raise FileParsingError(f"Could not parse CSV: {e}") from e

    if len(raw_df) > max_rows:
        raise FileParsingError(
            f"File has {len(raw_df):,} rows, which exceeds the {max_rows:,}-row limit. "
            "Trim the file or split it before uploading."
        )

    return build_flux_dataframe(raw_df)


def build_flux_dataframe(raw_df: pd.DataFrame) -> FluxDataFrame:
    """Infer + coerce a raw all-string DataFrame into a typed FluxDataFrame.

    Shared by the CSV and XLSX read paths so both go through the same inference logic.
    """
    columns: list[Column] = []
    coerced: dict[str, pd.Series] = {}
    for col_name in raw_df.columns:
        name = str(col_name)
        series = raw_df[col_name].replace("", None)
        inferred = infer_column_type(series.tolist())
        columns.append(Column(name=name, type=inferred))
        coerced[name] = _coerce_series(series, inferred)

    df = pd.DataFrame(coerced)
    schema = DataSchema(columns=columns)
    return FluxDataFrame(schema=schema, df=df, total_row_count=len(df))


def _coerce_series(series: pd.Series, dtype: DataType) -> pd.Series:
    if dtype == DataType.NUMBER:
        return pd.to_numeric(series, errors="coerce")
    if dtype == DataType.DATE:
        return pd.to_datetime(series, errors="coerce")
    if dtype == DataType.BOOLEAN:
        return series.map(_to_bool)
    return series


def _to_bool(value) -> Optional[bool]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("true", "yes"):
        return True
    if text in ("false", "no"):
        return False
    return None


def sanitize_cell_for_export(value):
    """Prefix formula-injection-triggering values with a single quote (PLAN.md §11).

    Cells beginning with =, +, -, or @ get reinterpreted as formulas when a CSV/XLSX is
    later opened in Excel — the standard CSV/formula-injection vulnerability. Only string
    cells are touched; numeric columns (e.g. legitimate negative numbers) keep their dtype
    and are never written as leading-'-' text in the first place.
    """
    if isinstance(value, str) and value.startswith(_INJECTION_PREFIXES):
        return "'" + value
    return value


def write_csv(df: pd.DataFrame) -> str:
    """Serialize a DataFrame to CSV text, sanitized against formula injection on export."""
    sanitized = df.map(sanitize_cell_for_export)
    return sanitized.to_csv(index=False)
