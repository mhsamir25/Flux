import pandas as pd

from app.engine.error_messages import extract_row_indices, suggest_fix, to_plain_english


def test_key_error_translated_and_suggests_fix():
    error = KeyError("region")
    message = to_plain_english(error)
    assert "region" in message
    assert "not found" in message
    assert "spelled correctly" in suggest_fix(error)


def test_out_of_bounds_datetime_suggests_convert_type():
    error = pd.errors.OutOfBoundsDatetime("bad date")
    assert "date" in to_plain_english(error).lower()
    assert "Convert Type" in suggest_fix(error)


def test_zero_division_suggests_filter():
    error = ZeroDivisionError()
    assert "Division by zero" in to_plain_english(error)
    assert "Filter" in suggest_fix(error)


def test_value_error_uses_message_text():
    error = ValueError("'abc' is not a valid number")
    assert to_plain_english(error) == "'abc' is not a valid number"


def test_value_error_empty_message_falls_back():
    error = ValueError()
    assert to_plain_english(error) == "Invalid value encountered while running this step."


def test_type_error_translated():
    error = TypeError("unsupported operand type(s)")
    assert "type mismatch" in to_plain_english(error)


def test_unknown_exception_falls_back_generically():
    error = RuntimeError("something odd")
    assert "unexpected error" in to_plain_english(error).lower()
    assert suggest_fix(error) is None


def test_extract_row_indices_always_none():
    assert extract_row_indices(ValueError("x")) is None
    assert extract_row_indices(KeyError("x")) is None
