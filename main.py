#!/usr/bin/env python3
"""
Pat.AI - 특허분석 AI 시스템
RAG 기반 특허 검색 및 분석 플랫폼
"""

import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
