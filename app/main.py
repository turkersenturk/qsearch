"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import ingest, search
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting qsearch API server...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"Qdrant URL: {settings.qdrant_url}")

    yield

    # Shutdown
    logger.info("Shutting down qsearch API server...")


# Create FastAPI app
app = FastAPI(
    title="QSearch API",
    description="Document processing and RAG (Retrieval-Augmented Generation) API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router)
app.include_router(search.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "qsearch",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "qsearch-api"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development"
    )
