# QSearch - Document Processing & RAG API

Asynchronous FastAPI service developed for document processing and RAG (Retrieval-Augmented Generation).

## Features

- **Asynchronous Document Processing**: Background document processing with Celery
- **Docling Integration**: Process PDF and other document formats
- **Vector Search**: Semantic similarity search with Qdrant
- **RESTful API**: Modern and fast API with FastAPI
- **Scalable**: Horizontally scalable architecture with Redis and Celery

## Technology Stack

- **Python 3.10+**
- **FastAPI**: Modern web framework
- **Celery**: Asynchronous task queue
- **Redis**: Message broker and result backend
- **Qdrant**: Vector database
- **Docling**: Document processing and chunking
- **Docker & Docker Compose**: Containerization

## Quick Start

### Method 1: One Command with Docker (Recommended)

```bash
# Clone the repository
git clone git@github.com:turkersenturk/qsearch.git
cd qsearch

# Start the entire stack (API + Worker + Redis + Qdrant)
docker-compose up -d

# Watch logs
docker-compose logs -f
```

**Ready!** API is running at http://localhost:8000


```bash
# Start with Flower included
docker-compose --profile monitoring up -d
```

#### Services

| Service        | URL                        | Description                  |
|----------------|----------------------------|------------------------------|
| API            | http://localhost:8000      | FastAPI REST API             |
| API Docs       | http://localhost:8000/docs | Swagger UI                   |
| Qdrant         | http://localhost:6333      | Vector Database              |
| Redis          | localhost:6379             | Message Broker               |
| Flower         | http://localhost:5555      | Celery Monitoring (optional) |

### Method 2: Local Development (Manual)

For local development without Docker:

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Environment setup
cp .env.example .env

# 4. Start only Redis and Qdrant in Docker
docker-compose up -d redis qdrant

# 5. Start API (Terminal 1)
uvicorn app.main:app --reload --port 8000

# 6. Start Worker (Terminal 2)
celery -A app.worker.celery_app worker --loglevel=info --concurrency=2

# 7. (Optional) Flower (Terminal 3)
celery -A app.worker.celery_app flower
```

## API Usage

### Upload Document (URL)

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/document.pdf",
    "metadata": {"category": "research"}
  }'
```

Response:
```json
{
  "task_id": "abc123...",
  "status": "accepted",
  "message": "Document ingestion started for URL: https://example.com/document.pdf"
}
```

### Upload Document (File)

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/file" \
  -F "file=@/path/to/document.pdf" \
  -F 'metadata={"category": "research"}'
```

### Check Task Status

```bash
curl "http://localhost:8000/api/v1/task/abc123..."
```

Response:
```json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "message": "Task completed successfully",
  "result": {
    "status": "success",
    "num_chunks": 42,
    "source": "https://example.com/document.pdf"
  }
}
```

### Semantic Search

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "limit": 5,
    "score_threshold": 0.7
  }'
```

Response:
```json
{
  "query": "machine learning algorithms",
  "count": 3,
  "results": [
    {
      "text": "Machine learning is a subset of artificial intelligence...",
      "source": "https://example.com/document.pdf",
      "score": 0.89,
      "metadata": {
        "chunk_index": 5,
        "category": "research"
      }
    }
  ]
}
```

### Delete Document

```bash
curl -X DELETE "http://localhost:8000/api/v1/document?source=https://example.com/document.pdf"
```

## API Documentation

Interactive API documentation is available when the service is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
qsearch/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── worker.py            # Celery configuration
│   ├── api/                 # API endpoints
│   │   ├── ingest.py        # Document ingestion endpoints
│   │   └── search.py        # Search endpoints
│   ├── core/                # Core configuration
│   │   └── config.py        # Environment settings
│   ├── services/            # Business logic services
│   │   ├── docling.py       # Docling processing service
│   │   └── qdrant.py        # Qdrant database service
│   └── tasks/               # Celery tasks
│       └── process.py       # Document processing tasks
├── tests/                   # Test files
├── docker-compose.yml       # Docker services
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment file
└── README.md               # This file
```

## Development

### Docker Commands

```bash
# Managing services
docker-compose ps                    # Running services
docker-compose logs -f api           # API logs
docker-compose logs -f celery-worker # Worker logs
docker-compose restart celery-worker # Restart worker
docker-compose down                  # Stop all services
docker-compose down -v               # Delete volumes too

# Rebuilding images
docker-compose build                 # All images
docker-compose build --no-cache      # Without cache
docker-compose up -d --build         # Build and start

# Connecting to containers
docker-compose exec api bash         # API container
docker-compose exec celery-worker bash # Worker container

# Resource usage
docker stats
```

### Running Tests

```bash
# Local
pytest

# Inside Docker
docker-compose exec api pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
black .
```

## Notes

- **Memory Usage**: Since Docling is memory-intensive, Celery worker concurrency should be kept low (2-4)
- **Embedding Model**: By default, `all-MiniLM-L6-v2` (768-dimensional vectors) is used
- **Vector Dimension**: If using a different embedding model, update the vector dimension in [qdrant.py](app/services/qdrant.py)
- **Production**: Configure CORS settings and other security settings for production

## License

GNU General Public License v3.0
