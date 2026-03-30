"""
Custom exception hierarchy for OCR Server.

All custom exceptions inherit from OCRServerException for easy catching.
"""


class OCRServerException(Exception):
    """Base exception for all OCR Server errors."""

    def __init__(self, message: str = "An error occurred in OCR Server"):
        self.message = message
        super().__init__(self.message)


class DocumentNotFoundException(OCRServerException):
    """Raised when a document record is not found in the database."""

    def __init__(self, file_id: str):
        self.file_id = file_id
        super().__init__(f"Document with id '{file_id}' not found")


class ValidationException(OCRServerException):
    """Raised for input validation errors."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class StorageException(OCRServerException):
    """Raised for storage-related errors (MinIO/S3)."""

    def __init__(
        self, message: str = "Storage error", original_error: Exception = None
    ):
        self.original_error = original_error
        super().__init__(message)


class ExtractionException(OCRServerException):
    """Raised for document extraction errors (Docling/AI)."""

    def __init__(
        self, message: str = "Extraction error", original_error: Exception = None
    ):
        self.original_error = original_error
        super().__init__(message)
