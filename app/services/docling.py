"""Docling service for document processing and chunking."""
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import tempfile
import httpx
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.chunking import HybridChunker
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Set environment variables to prevent threading issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"


class DoclingService:
    """Service for processing documents using Docling."""

    _embedding_model = None  # Class-level cache for embedding model

    def __init__(self):
        """Initialize Docling converter and embedding model."""
        # Initialize document converter with PDF pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        # DocumentConverter supports multiple formats: PDF, HTML, DOCX, PPTX, MD, etc.
        # We only configure PDF options; other formats use defaults
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Initialize chunker
        self.chunker = HybridChunker(
            tokenizer="sentence-transformers/all-MiniLM-L6-v2",
            max_tokens=512
        )

        logger.info("DoclingService initialized successfully")

    @property
    def embedding_model(self):
        """Lazy load embedding model (singleton pattern)."""
        if DoclingService._embedding_model is None:
            logger.info("Loading embedding model...")
            DoclingService._embedding_model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device="cpu"  # Force CPU to avoid GPU issues
            )
            logger.info("Embedding model loaded successfully")
        return DoclingService._embedding_model

    async def download_file(self, url: str) -> Optional[Path]:
        """
        Download file from URL to temporary location.

        Args:
            url: URL to download from

        Returns:
            Path to downloaded file or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                logger.info(f"Downloaded content type: {content_type}")

                # Determine file suffix based on content type
                if "html" in content_type or "text/html" in content_type:
                    suffix = ".html"
                elif "pdf" in content_type or "application/pdf" in content_type:
                    suffix = ".pdf"
                elif "markdown" in content_type or "text/markdown" in content_type:
                    suffix = ".md"
                else:
                    # Try to get from URL, fallback to content inspection
                    suffix = Path(url).suffix
                    if not suffix:
                        # If it looks like HTML content, treat as HTML
                        content_preview = response.content[:1000].decode('utf-8', errors='ignore').lower()
                        if '<html' in content_preview or '<!doctype html' in content_preview:
                            suffix = ".html"
                        else:
                            suffix = ".pdf"  # Default fallback

                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file.write(response.content)
                temp_file.close()

                logger.info(f"Downloaded file from {url} to {temp_file.name} (type: {suffix})")
                return Path(temp_file.name)

        except Exception as e:
            logger.error(f"Error downloading file from {url}: {e}")
            return None

    def process_document(
        self,
        file_path: Path,
        source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Process document using Docling converter.

        Args:
            file_path: Path to document file
            source: Original source (URL or file path)

        Returns:
            Processed document data including DoclingDocument object or None if failed
        """
        try:
            logger.info(f"Processing document: {file_path}")

            # Convert document
            result = self.converter.convert(str(file_path))

            if not result or not result.document:
                logger.error("Document conversion failed")
                return None

            doc_data = {
                "source": source,
                "document": result.document,  # Keep the DoclingDocument object for chunking
                "text": result.document.export_to_markdown(),
                "metadata": {
                    "num_pages": getattr(result.document, "num_pages", None),
                    "title": getattr(result.document, "title", None),
                }
            }

            logger.info(f"Successfully processed document from {source}")
            return doc_data

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return None

    def chunk_document(self, doc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk document using Docling chunker.

        Args:
            doc_data: Document data with 'document' (DoclingDocument object) and 'metadata'

        Returns:
            List of chunks with text and metadata
        """
        try:
            # Get the DoclingDocument object
            document = doc_data.get("document")
            if not document:
                logger.warning("No document object found for chunking")
                return []

            # Create chunks using the DoclingDocument object
            chunks = []
            chunk_iter = self.chunker.chunk(document)

            for idx, chunk in enumerate(chunk_iter):
                chunk_data = {
                    "text": chunk.text,
                    "metadata": {
                        "chunk_index": idx,
                        "source": doc_data.get("source"),
                        **(doc_data.get("metadata", {}))
                    }
                }
                chunks.append(chunk_data)

            logger.info(f"Created {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error chunking document: {e}")
            return []

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for chunks.

        Args:
            chunks: List of chunks with 'text' key

        Returns:
            List of chunks with added 'embedding' key
        """
        try:
            if not chunks:
                return []

            # Extract texts
            texts = [chunk["text"] for chunk in chunks]

            # Generate embeddings in batch
            embeddings = self.embedding_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            # Add embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding.tolist()

            logger.info(f"Generated embeddings for {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    async def process_url(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Process document from URL: download, convert, chunk, and embed.

        Args:
            url: URL to document

        Returns:
            List of chunks with embeddings or None if failed
        """
        temp_file = None
        try:
            # Download file
            temp_file = await self.download_file(url)
            if not temp_file:
                return None

            # Process document
            doc_data = self.process_document(temp_file, url)
            if not doc_data:
                return None

            # Chunk document
            chunks = self.chunk_document(doc_data)
            if not chunks:
                return None

            # Embed chunks
            embedded_chunks = self.embed_chunks(chunks)
            return embedded_chunks

        finally:
            # Clean up temporary file
            if temp_file and temp_file.exists():
                temp_file.unlink()
                logger.info(f"Cleaned up temporary file: {temp_file}")

    def process_local_file(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Process local document file: convert, chunk, and embed.

        Args:
            file_path: Path to local file

        Returns:
            List of chunks with embeddings or None if failed
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Process document
            doc_data = self.process_document(path, file_path)
            if not doc_data:
                return None

            # Chunk document
            chunks = self.chunk_document(doc_data)
            if not chunks:
                return None

            # Embed chunks
            embedded_chunks = self.embed_chunks(chunks)
            return embedded_chunks

        except Exception as e:
            logger.error(f"Error processing local file {file_path}: {e}")
            return None

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        try:
            embedding = self.embedding_model.encode(
                query,
                convert_to_numpy=True
            )
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            return []


# Global instance
docling_service = DoclingService()
