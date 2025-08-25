"""Database models package."""

from .database import (
    Document,
    SearchHistory,
    User,
    create_default_admin,
    get_db,
    init_db,
)

__all__ = [
    "User",
    "Document",
    "SearchHistory",
    "get_db",
    "init_db",
    "create_default_admin",
]
