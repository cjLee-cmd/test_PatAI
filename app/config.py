"""Application configuration settings."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: str = "sqlite:///./data/patai.db"
    
    # AI Models
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-3.5-turbo"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    # Vector Database
    chroma_db_path: str = "./data/vectordb"
    
    # File Upload
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list = [".pdf"]
    upload_path: str = "./data/documents"
    
    # App Settings
    app_name: str = "Pat.AI"
    app_version: str = "0.1.0"
    debug: bool = True
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()