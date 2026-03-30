"""
Validation utilities — input validation helpers.
"""

import uuid

from core.exceptions import ValidationException


def validate_uuid(file_id: str) -> None:
    """Validate that a string is a valid UUID. Raises ValidationException if not."""
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise ValidationException(f"Invalid file ID format: {file_id}")
