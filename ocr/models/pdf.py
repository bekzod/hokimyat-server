"""
Document SQLAlchemy ORM model.

Represents uploaded documents and their processing status.
"""

import enum
import uuid as uuid_pkg

from sqlalchemy import Column, String, Enum, DateTime, JSON, Integer, Text, func

from core.database import Base


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    file_hash = Column(String, primary_key=True, index=True, unique=True)
    uuid = Column(String, index=True, unique=True, default=lambda: str(uuid_pkg.uuid4()))
    status = Column(Enum(DocumentStatus), default=DocumentStatus.processing)
    error_message = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    total_page_count = Column(Integer, nullable=True)
    meta = Column(JSON, nullable=True)
    manual_input = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
