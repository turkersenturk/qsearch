"""Qdrant vector database service for document storage and search."""
import logging
import hashlib
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    SearchParams,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Service for interacting with Qdrant vector database."""

    def __init__(self):
        """Initialize Qdrant client and ensure collection exists."""
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection_name = settings.qdrant_collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                # Using 384 dimensions for all-MiniLM-L6-v2 model
                # If you use a different embedding model, adjust this size accordingly
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=384,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection {self.collection_name} created successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Insert or update document chunks in Qdrant.

        Args:
            chunks: List of chunks with 'text' and 'embedding' keys
            source: Source URL or file path
            metadata: Additional metadata to attach to all chunks

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            points = []
            for idx, chunk in enumerate(chunks):
                # Generate deterministic positive integer ID using hash
                # Qdrant requires positive integers or UUID
                hash_input = f"{source}_{idx}".encode('utf-8')
                point_id = int(hashlib.sha256(hash_input).hexdigest()[:16], 16)
                payload = {
                    "text": chunk.get("text", ""),
                    "source": source,
                    "chunk_index": idx,
                    **(metadata or {})
                }

                # Add chunk-specific metadata if available (only serializable types)
                if "metadata" in chunk:
                    chunk_metadata = chunk["metadata"]
                    # Filter out non-serializable objects
                    serializable_metadata = {
                        k: v for k, v in chunk_metadata.items()
                        if isinstance(v, (str, int, float, bool, list, dict, type(None)))
                    }
                    payload.update(serializable_metadata)

                # Ensure embedding is a list (not numpy array or other)
                embedding = chunk["embedding"]
                if not isinstance(embedding, list):
                    embedding = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
                points.append(point)

            # Batch upsert
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )

            logger.info(f"Successfully upserted {len(points)} chunks from {source}")
            return True

        except Exception as e:
            logger.error(f"Error upserting chunks to Qdrant: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents in Qdrant.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            filters: Optional filters to apply to the search

        Returns:
            List of search results with text, source, and score
        """
        try:
            search_params = SearchParams(
                exact=False,
                hnsw_ef=128
            )

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                search_params=search_params,
                query_filter=Filter(**filters) if filters else None
            )

            formatted_results = []
            for result in results:
                formatted_results.append({
                    "text": result.payload.get("text", ""),
                    "source": result.payload.get("source", ""),
                    "score": result.score,
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["text", "source"]
                    }
                })

            logger.info(f"Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error searching in Qdrant: {e}")
            return []

    def delete_by_source(self, source: str) -> bool:
        """
        Delete all chunks from a specific source.

        Args:
            source: Source URL or file path to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={
                    "filter": {
                        "must": [
                            {
                                "key": "source",
                                "match": {"value": source}
                            }
                        ]
                    }
                }
            )
            logger.info(f"Deleted all chunks from source: {source}")
            return True

        except Exception as e:
            logger.error(f"Error deleting chunks from Qdrant: {e}")
            return False


# Global instance
qdrant_service = QdrantService()
