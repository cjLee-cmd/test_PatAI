"""Document processing service for PDF files."""

from typing import Dict, List

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.models.database import Document


class DocumentProcessor:
    """Document processing and embedding service."""

    def __init__(self):
        # Lazy initialization to avoid startup delays
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None

    def _init_models(self):
        """Initialize models on first use."""
        if self.embedding_model is None:
            print("Loading embedding model...")
            self.embedding_model = SentenceTransformer(settings.embedding_model)
            print("Embedding model loaded successfully")

        if self.chroma_client is None:
            print("Initializing ChromaDB...")
            self.chroma_client = chromadb.PersistentClient(
                path=settings.chroma_db_path,
                settings=Settings(anonymized_telemetry=False),
            )

            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="patent_documents",
                metadata={"description": "Patent documents collection"},
            )
            print("ChromaDB initialized successfully")

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from PDF file."""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            error_msg = str(e)
            if (
                "Stream has ended unexpectedly" in error_msg
                or "EOF marker not found" in error_msg
            ):
                raise ValueError(
                    "유효하지 않거나 손상된 PDF 파일입니다. 올바른 PDF 파일을 업로드해주세요."
                )
            elif "invalid pdf header" in error_msg:
                raise ValueError("PDF 파일이 아닙니다. 실제 PDF 파일을 업로드해주세요.")
            elif "PdfStreamError" in str(type(e)) or "pypdf" in error_msg.lower():
                raise ValueError(
                    "파일 형식이 올바르지 않습니다. 유효한 PDF 파일을 업로드해주세요."
                )
            else:
                raise ValueError(f"PDF 파일 처리 중 오류가 발생했습니다: {error_msg}")

    def chunk_text(
        self, text: str, chunk_size: int = 1000, overlap: int = 200
    ) -> List[str]:
        """Split text into overlapping chunks."""
        # Simple sentence-based chunking
        sentences = text.split(".")
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Add overlap
                    overlap_text = (
                        current_chunk[-overlap:]
                        if len(current_chunk) > overlap
                        else current_chunk
                    )
                    current_chunk = overlap_text + sentence + ". "
                else:
                    current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [
            chunk for chunk in chunks if len(chunk.strip()) > 50
        ]  # Filter too short chunks

    def process_document(self, document: Document, file_path: str) -> int:
        """Process a document and store embeddings."""
        self._init_models()  # Initialize models on first use
        try:
            # Extract text from PDF
            text = self.extract_text_from_pdf(file_path)

            # Chunk the text
            chunks = self.chunk_text(text)

            # Generate embeddings
            embeddings = self.embedding_model.encode(chunks).tolist()

            # Create unique IDs for chunks
            chunk_ids = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{document.id}_{i}"
                chunk_ids.append(chunk_id)
                metadatas.append(
                    {
                        "document_id": document.id,
                        "filename": document.filename,
                        "chunk_index": i,
                        "chunk_text": chunk,
                    }
                )

            # Store in ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
                ids=chunk_ids,
            )

            return len(chunks)

        except Exception as e:
            error_msg = str(e)
            # Check if it's a PDF processing error from extract_text_from_pdf
            if "유효하지 않거나 손상된" in error_msg or "PDF 파일이 아닙" in error_msg:
                raise ValueError(error_msg)  # Pass through the localized message
            elif (
                "Failed to extract text from PDF" in error_msg
                or "pypdf" in error_msg.lower()
            ):
                raise ValueError(
                    "문서 처리 중 오류가 발생했습니다. PDF 파일이 올바른지 확인해주세요."
                )
            else:
                raise ValueError(
                    f"문서 처리 중 예기치 못한 오류가 발생했습니다: {error_msg}"
                )

    def search_similar_chunks(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for similar chunks based on query."""
        self._init_models()  # Initialize models on first use
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query]).tolist()

            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )

            # Format results
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "chunk_id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1
                        - results["distances"][0][i],  # Convert distance to similarity
                    }
                )

            return formatted_results

        except Exception as e:
            error_msg = str(e)
            if "collection" in error_msg.lower() or "chroma" in error_msg.lower():
                raise ValueError(
                    "검색 데이터베이스에 문제가 있습니다. 관리자에게 문의해주세요."
                )
            else:
                raise ValueError(f"검색 중 오류가 발생했습니다: {error_msg}")

    def delete_document_chunks(self, document_id: int):
        """Delete all chunks for a document."""
        self._init_models()  # Initialize models on first use
        try:
            # Query all chunks for the document
            results = self.collection.get(where={"document_id": document_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])

        except Exception as e:
            error_msg = str(e)
            if "collection" in error_msg.lower() or "chroma" in error_msg.lower():
                raise ValueError("문서 삭제 중 데이터베이스 오류가 발생했습니다.")
            else:
                raise ValueError(f"문서 삭제 중 오류가 발생했습니다: {error_msg}")


# Global document processor instance
document_processor = DocumentProcessor()
