#!/bin/bash
# Start Celery worker with optimized settings for Docling + PyTorch

# Set environment variables to prevent segmentation faults
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Start worker with solo pool (single process, no forking issues)
celery -A app.worker.celery_app worker \
  --loglevel=info \
  --pool=solo \
  --max-tasks-per-child=1

# Alternative: Use prefork with single concurrency
# celery -A app.worker.celery_app worker \
#   --loglevel=info \
#   --pool=prefork \
#   --concurrency=1 \
#   --max-tasks-per-child=1
