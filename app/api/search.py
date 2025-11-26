"""API endpoints for document search."""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.docling import docling_service
from app.services.qdrant import qdrant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


class SearchRequest(BaseModel):
    """Request model for search."""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(5, ge=1, le=100, description="Maximum number of results")
    score_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold"
    )
    filters: Optional[dict] = Field(
        None,
        description="Optional filters to apply to search"
    )


class SearchResult(BaseModel):
    """Model for a single search result."""
    text: str
    source: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    """Response model for search."""
    query: str
    results: List[SearchResult]
    count: int


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Search for documents using semantic similarity.

    The query is embedded using the same model as the documents,
    and similar chunks are retrieved from Qdrant.

    Args:
        request: Search query and parameters

    Returns:
        List of relevant document chunks with similarity scores
    """
    try:
        logger.info(f"Received search request: {request.query}")

        # Generate query embedding
        query_embedding = docling_service.embed_query(request.query)

        if not query_embedding:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate query embedding"
            )

        # Search in Qdrant
        results = qdrant_service.search(
            query_vector=query_embedding,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filters=request.filters
        )

        # Format response
        search_results = [
            SearchResult(
                text=result["text"],
                source=result["source"],
                score=result["score"],
                metadata=result["metadata"]
            )
            for result in results
        ]

        response = SearchResponse(
            query=request.query,
            results=search_results,
            count=len(search_results)
        )

        logger.info(f"Search completed: found {len(search_results)} results")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        Status of the API service
    """
    return {
        "status": "healthy",
        "service": "qsearch-api"
    }
