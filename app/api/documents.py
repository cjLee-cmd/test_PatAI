"""Document management API endpoints."""

import os
import shutil
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_dependency
from app.config import settings
from app.models import Document, User, get_db
from app.services.document_processor import document_processor

router = APIRouter()


def validate_pdf_file(file_path: str) -> bool:
    """Validate that the file is actually a PDF by checking its header."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
            return header == b"%PDF"
    except Exception:
        return False


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    upload_date: str
    processed: bool
    chunk_count: int


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Upload a PDF document."""
    # Check user permissions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can upload documents",
        )

    # Check file extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    # Check file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {settings.max_file_size} bytes",
        )

    try:
        # Create upload directory if it doesn't exist
        os.makedirs(settings.upload_path, exist_ok=True)

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.upload_path, unique_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate that it's actually a PDF file
        if not validate_pdf_file(file_path):
            # Clean up invalid file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 PDF 파일입니다. 실제 PDF 파일을 업로드해주세요.",
            )

        # Create document record
        document = Document(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=file.size or os.path.getsize(file_path),
            uploaded_by=current_user.id,
            processed=False,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Return immediately and process in background (simplified for demo)
        return DocumentUploadResponse(
            message="Document uploaded successfully. Processing will begin shortly.",
            document=DocumentResponse(
                id=document.id,
                filename=document.filename,
                original_filename=document.original_filename,
                file_size=document.file_size,
                upload_date=document.upload_date.isoformat(),
                processed=document.processed,
                chunk_count=document.chunk_count,
            ),
        )

        # Note: Document processing happens manually via /process endpoint
        # In production, consider using background task queue (Celery, RQ, etc.)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """List all uploaded documents."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view documents",
        )

    documents = db.query(Document).order_by(Document.upload_date.desc()).all()

    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            upload_date=doc.upload_date.isoformat(),
            processed=doc.processed,
            chunk_count=doc.chunk_count,
        )
        for doc in documents
    ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Delete a document."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete documents",
        )

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    try:
        # Delete from vector database
        document_processor.delete_document_chunks(document_id)

        # Delete file from filesystem
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # Delete from database
        db.delete(document)
        db.commit()

        return {"message": "Document deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.post("/{document_id}/process")
async def process_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Process a document manually."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can process documents",
        )

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if document.processed:
        return {"message": "Document already processed"}

    try:
        chunk_count = document_processor.process_document(document, document.file_path)
        document.processed = True
        document.chunk_count = chunk_count
        db.commit()

        return {
            "message": "Document processed successfully",
            "chunk_count": chunk_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.post("/add-sample-data")
async def add_sample_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Add sample patent data for testing."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can add sample data",
        )

    try:
        # Sample patent data
        sample_documents = [
            {
                "title": "AI 기반 이미지 인식 시스템",
                "content": "본 발명은 딥러닝과 컴퓨터 비전 기술을 활용한 이미지 인식 시스템에 관한 것입니다. 합성곱 신경망(CNN)을 사용하여 높은 정확도의 이미지 분류를 수행합니다.",
            },
            {
                "title": "IoT 기반 스마트홈 시스템",
                "content": "사물인터넷 기술을 활용한 스마트홈 자동화 시스템입니다. 센서 네트워크와 무선통신을 통해 실시간 모니터링 및 제어가 가능합니다.",
            },
            {
                "title": "블록체인 기반 전자투표 시스템",
                "content": "블록체인 기술을 활용한 안전한 전자투표 시스템입니다. 분산원장 기술을 통해 투표의 투명성과 보안성을 보장합니다.",
            },
            {
                "title": "자율주행차 센서 융합 기술",
                "content": "라이다, 카메라, 레이더 센서를 융합한 자율주행 인지 시스템입니다. 다중 센서 데이터를 통해 정확한 환경 인식을 수행합니다.",
            },
            {
                "title": "양자암호통신 프로토콜",
                "content": "양자역학 원리를 활용한 절대 보안 통신 프로토콜입니다. 양자 얽힘과 불확정성 원리를 이용하여 도청 불가능한 통신을 구현합니다.",
            },
        ]

        # Initialize document processor
        document_processor._init_models()

        # Add each sample document
        for i, sample in enumerate(sample_documents):
            # Create document record
            document = Document(
                filename=f"sample_{i + 1}.pdf",
                original_filename=f"{sample['title']}.pdf",
                file_path=f"sample/sample_{i + 1}.pdf",
                file_size=1000,
                uploaded_by=current_user.id,
                processed=True,
                chunk_count=1,
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # Add to vector database
            embedding = document_processor.embedding_model.encode(
                [sample["content"]]
            ).tolist()

            document_processor.collection.add(
                embeddings=embedding,
                documents=[sample["content"]],
                metadatas=[
                    {
                        "document_id": document.id,
                        "filename": document.original_filename,
                        "chunk_index": 0,
                        "chunk_text": sample["content"],
                    }
                ],
                ids=[f"{document.id}_0"],
            )

        return {
            "message": f"Successfully added {len(sample_documents)} sample documents",
            "count": len(sample_documents),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add sample data: {str(e)}",
        )
