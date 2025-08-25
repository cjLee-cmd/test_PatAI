"""Tests for document processor service."""

import tempfile
import os
from unittest.mock import Mock, patch

import pytest

from app.services.document_processor import document_processor


class TestDocumentProcessor:
    """Test cases for DocumentProcessor class."""

    def test_validate_pdf_file_valid(self):
        """Test PDF validation with valid PDF header."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4')  # Valid PDF header
            f.write(b'some content')
            valid_pdf = f.name

        try:
            # Import after creating the file to avoid import issues
            from app.api.documents import validate_pdf_file
            assert validate_pdf_file(valid_pdf) is True
        finally:
            os.unlink(valid_pdf)

    def test_validate_pdf_file_invalid(self):
        """Test PDF validation with invalid content."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'Test PDF content')  # Invalid content
            invalid_pdf = f.name

        try:
            from app.api.documents import validate_pdf_file
            assert validate_pdf_file(invalid_pdf) is False
        finally:
            os.unlink(invalid_pdf)

    def test_extract_text_from_pdf_invalid_file(self):
        """Test PDF text extraction with invalid file."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'This is not a PDF file')
            fake_pdf = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                document_processor.extract_text_from_pdf(fake_pdf)
            
            assert "유효하지 않거나 손상된 PDF 파일입니다" in str(exc_info.value)
        finally:
            os.unlink(fake_pdf)

    def test_chunk_text_basic(self):
        """Test basic text chunking functionality."""
        # Use longer text that will create meaningful chunks
        text = "This is a longer sentence that should be enough to create a meaningful chunk. " * 5
        chunks = document_processor.chunk_text(text, chunk_size=200, overlap=20)
        
        assert len(chunks) > 0
        # All chunks should be longer than 50 characters (our filter threshold)
        assert all(len(chunk) > 50 for chunk in chunks)

    def test_chunk_text_empty(self):
        """Test chunking with empty text."""
        chunks = document_processor.chunk_text("", chunk_size=100, overlap=10)
        assert chunks == []