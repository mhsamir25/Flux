"""
Inference order is fixed: numeric, then date, then boolean literal, else string.
"""
from datetime import datetime
from typing import Iterable

from .schema import DataType

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)

_BOOLEAN_LITERALS = {"true", "false", "yes", "no", "1", "0"}


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def _is_date(text: str) -> bool:
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def infer_cell_type(value) -> DataType | None:
    """Infer the type of a single cell. Returns None for blank/missing values (uninformative)."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if _is_number(text):
        return DataType.NUMBER
    if _is_date(text):
        return DataType.DATE
    if text.lower() in _BOOLEAN_LITERALS:
        return DataType.BOOLEAN
    return DataType.STRING


def infer_column_type(values: Iterable) -> DataType:
    """Infer a single DataType for a column from a sample of its values.

    All non-blank values must agree on a type; otherwise falls back to STRING.
    An all-blank/empty sample also falls back to STRING.
    """
    inferred_types = {t for t in (infer_cell_type(v) for v in values) if t is not None}
    if len(inferred_types) == 1:
        return inferred_types.pop()
    return DataType.STRING
