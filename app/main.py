"""Main FastAPI application."""

import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api import auth, documents, search
from app.config import settings
from app.models import create_default_admin, get_db, init_db

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Pat.AI - RAG-based Patent Search System",
)

# Create directories
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)
os.makedirs("data/documents", exist_ok=True)
os.makedirs("data/vectordb", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(search.router, prefix="/api/search", tags=["search"])


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Initialize database
    init_db()

    # Create default admin user
    create_default_admin()

    print(f"{settings.app_name} v{settings.app_version} started successfully!")
    print("Default admin credentials: Admin/Admin")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Serve the admin page."""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/info")
async def app_info(db: Session = Depends(get_db)):
    """Get application information."""
    from app.models.database import Document, SearchHistory, User

    # Get basic stats
    total_users = db.query(User).count()
    total_documents = db.query(Document).count()
    total_searches = db.query(SearchHistory).count()
    processed_documents = db.query(Document).filter(Document.processed).count()

    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "stats": {
            "total_users": total_users,
            "total_documents": total_documents,
            "processed_documents": processed_documents,
            "total_searches": total_searches,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
