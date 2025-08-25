"""Document processing service for PDF files."""

import os
import hashlib
from typing import List, Dict, Tuple
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
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
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="patent_documents",
                metadata={"description": "Patent documents collection"}
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
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        # Simple sentence-based chunking
        sentences = text.split('.')
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
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = overlap_text + sentence + ". "
                else:
                    current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if len(chunk.strip()) > 50]  # Filter too short chunks
    
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
                metadatas.append({
                    "document_id": document.id,
                    "filename": document.filename,
                    "chunk_index": i,
                    "chunk_text": chunk
                })
            
            # Store in ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
                ids=chunk_ids
            )
            
            return len(chunks)
            
        except Exception as e:
            raise ValueError(f"Failed to process document: {str(e)}")
    
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
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "chunk_id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "similarity": 1 - results['distances'][0][i],  # Convert distance to similarity
                })
            
            return formatted_results
            
        except Exception as e:
            raise ValueError(f"Failed to search chunks: {str(e)}")
    
    def delete_document_chunks(self, document_id: int):
        """Delete all chunks for a document."""
        self._init_models()  # Initialize models on first use
        try:
            # Query all chunks for the document
            results = self.collection.get(
                where={"document_id": document_id}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                
        except Exception as e:
            raise ValueError(f"Failed to delete document chunks: {str(e)}")


# Global document processor instance
document_processor = DocumentProcessor()