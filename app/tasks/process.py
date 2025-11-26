"""Celery tasks for document processing."""
import logging
import asyncio
import os
from pathlib import Path
from typing import Optional
from celery import Task
from app.worker import celery_app
from app.services.docling import docling_service
from app.services.qdrant import qdrant_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Base task class with callbacks for task lifecycle events."""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed with error: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Task {task_id} is being retried due to: {exc}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="process_document",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_jitter=True
)
def process_document(
    self,
    source: str,
    source_type: str,
    metadata: Optional[dict] = None
) -> dict:
    """
    Process document from URL or local file and store in Qdrant.

    Args:
        source: URL or file path to document
        source_type: 'url' or 'file'
        metadata: Additional metadata to attach to chunks

    Returns:
        Dictionary with processing results
    """
    temp_file_path = None
    try:
        logger.info(f"Starting document processing: {source} (type: {source_type})")

        # Track temp file for cleanup
        if source_type == "file":
            temp_file_path = source

        # Process document based on source type
        if source_type == "url":
            # For async operations in sync Celery task, we need to create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                chunks = loop.run_until_complete(docling_service.process_url(source))
            finally:
                loop.close()
        elif source_type == "file":
            chunks = docling_service.process_local_file(source)
        else:
            raise ValueError(f"Invalid source_type: {source_type}")

        if not chunks:
            error_msg = f"Failed to process document: {source}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "source": source
            }

        # Store chunks in Qdrant
        success = qdrant_service.upsert_chunks(
            chunks=chunks,
            source=source,
            metadata=metadata
        )

        if not success:
            error_msg = f"Failed to store chunks in Qdrant for: {source}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "source": source
            }

        result = {
            "status": "success",
            "message": f"Successfully processed and stored {len(chunks)} chunks",
            "source": source,
            "num_chunks": len(chunks)
        }

        logger.info(f"Document processing completed: {source}")
        return result

    except Exception as e:
        error_msg = f"Error processing document {source}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Re-raise for Celery retry mechanism
        raise
    finally:
        # Clean up temporary file after processing (success or failure)
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                # Only delete if it's in shared temp directory (safety check)
                if str(Path(temp_file_path).parent) == str(settings.shared_temp_dir):
                    os.remove(temp_file_path)
                    logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file {temp_file_path}: {cleanup_error}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="delete_document",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30}
)
def delete_document(self, source: str) -> dict:
    """
    Delete all chunks from a specific source.

    Args:
        source: Source URL or file path to delete

    Returns:
        Dictionary with deletion results
    """
    try:
        logger.info(f"Deleting document: {source}")

        success = qdrant_service.delete_by_source(source)

        if success:
            result = {
                "status": "success",
                "message": f"Successfully deleted document: {source}",
                "source": source
            }
        else:
            result = {
                "status": "error",
                "message": f"Failed to delete document: {source}",
                "source": source
            }

        logger.info(f"Document deletion completed: {source}")
        return result

    except Exception as e:
        error_msg = f"Error deleting document {source}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise
