"""Search and RAG API endpoints."""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.models import get_db, User
from app.api.auth import get_current_user_dependency
from app.services.rag_service import rag_service

router = APIRouter()


class SearchRequest(BaseModel):
    query: str


class SearchSource(BaseModel):
    filename: str
    chunk_text: str
    similarity: float


class SearchResponse(BaseModel):
    query: str
    response: str
    sources: List[SearchSource]
    response_time: int
    search_id: int = None


class SearchHistoryItem(BaseModel):
    id: int
    query: str
    response: str
    sources: List[Dict]
    response_time: int
    created_at: str


@router.post("/ask", response_model=SearchResponse)
async def ask_question(
    query: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Ask a question and get an AI-powered response."""
    if not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )
    
    try:
        result = rag_service.ask_question(db, current_user, query.strip())
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["response"]
            )
        
        return SearchResponse(
            query=result["query"],
            response=result["response"],
            sources=[
                SearchSource(
                    filename=source["filename"],
                    chunk_text=source["chunk_text"],
                    similarity=source["similarity"]
                )
                for source in result["sources"]
            ],
            response_time=result["response_time"],
            search_id=result.get("search_id")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}"
        )


@router.get("/history", response_model=List[SearchHistoryItem])
async def get_search_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Get user's search history."""
    try:
        history = rag_service.get_search_history(db, current_user, limit)
        
        return [
            SearchHistoryItem(
                id=item["id"],
                query=item["query"],
                response=item["response"],
                sources=item["sources"],
                response_time=item["response_time"],
                created_at=item["created_at"]
            )
            for item in history
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get search history: {str(e)}"
        )


@router.delete("/history/{search_id}")
async def delete_search_history_item(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Delete a search history item."""
    from app.models.database import SearchHistory
    
    search_item = db.query(SearchHistory).filter(
        SearchHistory.id == search_id,
        SearchHistory.user_id == current_user.id
    ).first()
    
    if not search_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search history item not found"
        )
    
    try:
        db.delete(search_item)
        db.commit()
        return {"message": "Search history item deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete search history item: {str(e)}"
        )


@router.get("/stats")
async def get_search_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    """Get user's search statistics."""
    from app.models.database import SearchHistory
    from sqlalchemy import func
    
    try:
        # Total searches
        total_searches = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).count()
        
        # Average response time
        avg_response_time = db.query(
            func.avg(SearchHistory.response_time)
        ).filter(
            SearchHistory.user_id == current_user.id
        ).scalar() or 0
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        recent_date = datetime.now() - timedelta(days=7)
        recent_searches = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id,
            SearchHistory.created_at >= recent_date
        ).count()
        
        return {
            "total_searches": total_searches,
            "average_response_time": round(avg_response_time, 2),
            "recent_searches": recent_searches
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get search statistics: {str(e)}"
        )