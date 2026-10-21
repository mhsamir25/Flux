from typing import Optional

import pandas as pd


def to_plain_english(error: Exception) -> str:
    if isinstance(error, KeyError):
        missing = str(error).strip("'\"")
        return f"Column '{missing}' not found — check the upstream node's output columns."
    if isinstance(error, pd.errors.OutOfBoundsDatetime):
        return "One or more values are out of range to be interpreted as a date."
    if isinstance(error, ZeroDivisionError):
        return "Division by zero occurred while computing this step."
    if isinstance(error, NotImplementedError):
        return "This node doesn't support this operation."
    if isinstance(error, ValueError):
        return str(error) or "Invalid value encountered while running this step."
    if isinstance(error, TypeError):
        return f"A type mismatch occurred: {error}"
    return f"An unexpected error occurred: {error}"


def suggest_fix(error: Exception) -> Optional[str]:
    if isinstance(error, KeyError):
        return "Check that the column name is spelled correctly and exists in the upstream node's output."
    if isinstance(error, pd.errors.OutOfBoundsDatetime):
        return "Add a Convert Type node upstream to normalize this column to a valid date format."
    if isinstance(error, ZeroDivisionError):
        return "Add a Filter node upstream to exclude rows where the denominator is zero."
    return None


def extract_row_indices(error: Exception) -> Optional[list[int]]:
    return None
