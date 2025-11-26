#!/usr/bin/env python3
"""Test script for QSearch API."""
import requests
import json
import time
from typing import Optional


API_BASE_URL = "http://localhost:8000/api/v1"


def ingest_url(url: str, metadata: Optional[dict] = None) -> str:
    """Ingest document from URL."""
    response = requests.post(
        f"{API_BASE_URL}/ingest/url",
        json={"url": url, "metadata": metadata}
    )
    response.raise_for_status()
    result = response.json()
    print(f"✓ Ingestion started: {result['task_id']}")
    return result['task_id']


def check_task(task_id: str) -> dict:
    """Check task status."""
    response = requests.get(f"{API_BASE_URL}/task/{task_id}")
    response.raise_for_status()
    return response.json()


def wait_for_task(task_id: str, max_wait: int = 300) -> bool:
    """Wait for task to complete."""
    print(f"Waiting for task {task_id}...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        status = check_task(task_id)

        if status['status'] == 'SUCCESS':
            print(f"✓ Task completed successfully!")
            print(f"  Result: {json.dumps(status.get('result', {}), indent=2)}")
            return True
        elif status['status'] == 'FAILURE':
            print(f"✗ Task failed: {status.get('error', 'Unknown error')}")
            return False
        elif status['status'] in ['PENDING', 'STARTED']:
            print(f"  Status: {status['status']} - {status.get('message', '')}")
            time.sleep(5)
        else:
            print(f"  Unknown status: {status['status']}")
            time.sleep(5)

    print(f"✗ Task timed out after {max_wait} seconds")
    return False


def search(query: str, limit: int = 5, score_threshold: Optional[float] = None):
    """Search for documents."""
    payload = {
        "query": query,
        "limit": limit
    }
    if score_threshold:
        payload["score_threshold"] = score_threshold

    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")

    response = requests.post(
        f"{API_BASE_URL}/search",
        json=payload
    )
    response.raise_for_status()
    result = response.json()

    print(f"Found {result['count']} results:\n")

    for idx, item in enumerate(result['results'], 1):
        print(f"{idx}. [Score: {item['score']:.3f}]")
        print(f"   Text: {item['text'][:200]}...")
        print(f"   Source: {item['source']}")
        if item['metadata']:
            print(f"   Metadata: {json.dumps(item['metadata'], indent=6)}")
        print()

    return result


def main():
    """Main test function."""
    print("QSearch API Test Script")
    print("=" * 60)

    # Test 1: Health check
    print("\n1. Health Check...")
    response = requests.get(f"{API_BASE_URL}/health")
    print(f"   API Status: {response.json()}")

    # Test 2: Search with different queries
    print("\n2. Running Search Queries...")

    queries = [
        "Hugo nedir?",
        "Hugo kurulumu ve kullanımı",
        "Hugo static site generator özellikleri",
        "Hugo tema yapılandırması",
        "Hugo deployment ve hosting",
    ]

    for query in queries:
        try:
            search(query, limit=3, score_threshold=0.5)
        except Exception as e:
            print(f"Error searching '{query}': {e}\n")

    print("\n" + "=" * 60)
    print("Test completed!")


if __name__ == "__main__":
    main()
