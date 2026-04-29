"""Reusable field validators for Pydantic schemas."""
import re


def validate_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\s\-\(\)]", "", value)
    if not re.match(r"^\+?\d{7,15}$", cleaned):
        raise ValueError("Invalid phone number format.")
    return cleaned


def validate_employee_code(value: str) -> str:
    if not re.match(r"^[A-Z0-9\-]{2,20}$", value):
        raise ValueError("Employee code must be 2–20 uppercase alphanumeric characters.")
    return value
