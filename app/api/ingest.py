"""API endpoints for document ingestion."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl, field_validator
from app.worker import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])


class IngestURLRequest(BaseModel):
    """Request model for URL ingestion."""
    url: HttpUrl
    metadata: Optional[dict] = None

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate that URL is properly formatted."""
        url_str = str(v)
        if not url_str.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class IngestResponse(BaseModel):
    """Response model for ingestion requests."""
    task_id: str
    status: str
    message: str


@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_url(request: IngestURLRequest):
    """
    Ingest document from URL.

    The document will be downloaded, processed, chunked, and stored in Qdrant.
    Processing happens asynchronously in the background.

    Args:
        request: URL and optional metadata

    Returns:
        Task ID for tracking the ingestion progress
    """
    try:
        url_str = str(request.url)
        logger.info(f"Received URL ingestion request: {url_str}")

        # Send task to Celery
        task = celery_app.send_task(
            "process_document",
            args=[url_str, "url", request.metadata]
        )

        return IngestResponse(
            task_id=task.id,
            status="accepted",
            message=f"Document ingestion started for URL: {url_str}"
        )

    except Exception as e:
        logger.error(f"Error starting URL ingestion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start document ingestion: {str(e)}"
        )


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None)
):
    """
    Ingest document from uploaded file.

    The file will be saved temporarily, processed, chunked, and stored in Qdrant.
    Processing happens asynchronously in the background.

    Args:
        file: Document file to upload
        metadata: Optional metadata as JSON string

    Returns:
        Task ID for tracking the ingestion progress
    """
    try:
        logger.info(f"Received file ingestion request: {file.filename}")

        # Save file to shared directory (accessible by both API and Worker containers)
        import json
        import os
        from pathlib import Path
        from datetime import datetime

        # Ensure shared temp directory exists
        shared_dir = Path(settings.shared_temp_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)

        # Create unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = Path(file.filename).suffix if file.filename else ".pdf"
        filename = f"{timestamp}_{file.filename}" if file.filename else f"{timestamp}{suffix}"
        temp_path = shared_dir / filename

        # Save file
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        logger.info(f"File saved to shared directory: {temp_path}")

        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata JSON: {metadata}")

        # Add filename to metadata
        if metadata_dict is None:
            metadata_dict = {}
        metadata_dict["filename"] = file.filename

        # Send task to Celery with absolute path in shared volume
        task = celery_app.send_task(
            "process_document",
            args=[str(temp_path), "file", metadata_dict]
        )

        return IngestResponse(
            task_id=task.id,
            status="accepted",
            message=f"Document ingestion started for file: {file.filename}"
        )

    except Exception as e:
        logger.error(f"Error starting file ingestion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start document ingestion: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of an ingestion task.

    Args:
        task_id: Task ID returned from ingestion endpoint

    Returns:
        Current task status and result if completed
    """
    try:
        task = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task.state,
        }

        if task.state == "PENDING":
            response["message"] = "Task is waiting to be processed"
        elif task.state == "STARTED":
            response["message"] = "Task is being processed"
        elif task.state == "SUCCESS":
            response["message"] = "Task completed successfully"
            response["result"] = task.result
        elif task.state == "FAILURE":
            response["message"] = "Task failed"
            response["error"] = str(task.info)
        elif task.state == "RETRY":
            response["message"] = "Task is being retried"
        else:
            response["message"] = f"Task state: {task.state}"

        return response

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.delete("/document")
async def delete_document(source: str):
    """
    Delete all chunks from a specific document source.

    Args:
        source: Source URL or file path to delete

    Returns:
        Task ID for tracking the deletion progress
    """
    try:
        logger.info(f"Received document deletion request: {source}")

        # Send task to Celery
        task = celery_app.send_task(
            "delete_document",
            args=[source]
        )

        return {
            "task_id": task.id,
            "status": "accepted",
            "message": f"Document deletion started for: {source}"
        }

    except Exception as e:
        logger.error(f"Error starting document deletion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start document deletion: {str(e)}"
        )
