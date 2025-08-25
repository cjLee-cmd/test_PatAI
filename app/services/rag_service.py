"""RAG (Retrieval-Augmented Generation) service."""

import json
from typing import List, Dict, Tuple
from datetime import datetime
import openai
from sqlalchemy.orm import Session
from app.config import settings
from app.models.database import SearchHistory, User
from app.services.document_processor import document_processor


class RAGService:
    """RAG service for question answering with document retrieval."""
    
    def __init__(self):
        # Initialize OpenAI client
        if settings.openai_api_key:
            openai.api_key = settings.openai_api_key
        else:
            print("Warning: OpenAI API key not set. Using mock responses.")
    
    def generate_response(self, query: str, context_chunks: List[Dict]) -> str:
        """Generate response using retrieved context and LLM."""
        try:
            # Prepare context from retrieved chunks
            context = "\n\n".join([
                f"문서: {chunk['metadata']['filename']}\n내용: {chunk['text']}"
                for chunk in context_chunks
            ])
            
            # Create prompt for the LLM
            prompt = f"""다음 문서들을 참고하여 질문에 답변해주세요.

문서 내용:
{context}

질문: {query}

답변 시 다음 사항을 준수해주세요:
1. 제공된 문서 내용을 바탕으로 정확하게 답변하세요.
2. 문서에 없는 내용은 추측하지 마세요.
3. 특허 관련 전문 용어는 쉽게 설명해주세요.
4. 답변 근거가 되는 문서를 명시해주세요.

답변:"""

            # Use OpenAI API if available, otherwise use mock response
            if settings.openai_api_key:
                response = openai.ChatCompletion.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": "당신은 특허 문서 전문가입니다. 주어진 문서를 바탕으로 정확하고 도움이 되는 답변을 제공하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            else:
                # Mock response for development
                return f"""[개발 모드] 질문 '{query}'에 대한 답변입니다.

검색된 문서에서 관련 정보를 찾았습니다:
{', '.join([chunk['metadata']['filename'] for chunk in context_chunks])}

실제 운영 환경에서는 GPT 모델이 이 문서들을 분석하여 상세한 답변을 제공합니다.

검색된 상위 결과:
{context_chunks[0]['text'][:200] + '...' if context_chunks else '관련 문서를 찾지 못했습니다.'}
"""
                
        except Exception as e:
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    def ask_question(self, db: Session, user: User, query: str) -> Dict:
        """Process a question and return answer with sources."""
        start_time = datetime.now()
        
        try:
            # Search for relevant chunks
            relevant_chunks = document_processor.search_similar_chunks(
                query=query, 
                n_results=5
            )
            
            # Generate response
            response = self.generate_response(query, relevant_chunks)
            
            # Calculate response time
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Prepare source information
            sources = [
                {
                    "filename": chunk['metadata']['filename'],
                    "chunk_text": chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    "similarity": round(chunk['similarity'], 3)
                }
                for chunk in relevant_chunks
            ]
            
            # Save to search history
            search_record = SearchHistory(
                user_id=user.id,
                query=query,
                response=response,
                sources=json.dumps(sources, ensure_ascii=False),
                response_time=response_time
            )
            db.add(search_record)
            db.commit()
            
            return {
                "query": query,
                "response": response,
                "sources": sources,
                "response_time": response_time,
                "search_id": search_record.id
            }
            
        except Exception as e:
            error_msg = f"질문 처리 중 오류가 발생했습니다: {str(e)}"
            return {
                "query": query,
                "response": error_msg,
                "sources": [],
                "response_time": int((datetime.now() - start_time).total_seconds() * 1000),
                "error": True
            }
    
    def get_search_history(self, db: Session, user: User, limit: int = 20) -> List[Dict]:
        """Get user's search history."""
        history = db.query(SearchHistory).filter(
            SearchHistory.user_id == user.id
        ).order_by(
            SearchHistory.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": record.id,
                "query": record.query,
                "response": record.response,
                "sources": json.loads(record.sources) if record.sources else [],
                "response_time": record.response_time,
                "created_at": record.created_at.isoformat()
            }
            for record in history
        ]


# Global RAG service instance
rag_service = RAGService()