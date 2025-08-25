"""Database models package."""

from .database import User, Document, SearchHistory, get_db, init_db, create_default_admin

__all__ = ["User", "Document", "SearchHistory", "get_db", "init_db", "create_default_admin"]