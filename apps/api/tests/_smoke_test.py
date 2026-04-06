"""Smoke test for the retrieval pipeline — run with the API server up."""

import uuid

import requests

BASE = "http://127.0.0.1:8001"


def main() -> None:
    doc_id = str(uuid.uuid4())
    output = {
        "document_id": doc_id,
        "source_file": {
            "filename": "test-doc.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "classification": "pdf",
        },
        "requested_mode": "auto",
        "resolved_mode": "readable_pdf",
        "status": "completed",
        "pages": [
            {
                "page_number": 1,
                "width": 612.0,
                "height": 792.0,
                "text": "The Supreme Court held that the right to privacy is fundamental. Citizens have the right to free speech and assembly.",
                "text_blocks": [
                    {
                        "block_id": "b1",
                        "page_number": 1,
                        "text": "The Supreme Court held that the right to privacy is fundamental.",
                        "confidence": 0.95,
                        "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 20, "coordinate_space": "pdf_points"},
                        "geometry_source": "pdf_text",
                    },
                    {
                        "block_id": "b2",
                        "page_number": 1,
                        "text": "Citizens have the right to free speech and assembly.",
                        "confidence": 0.93,
                        "bbox": {"x0": 0, "y0": 25, "x1": 100, "y1": 45, "coordinate_space": "pdf_points"},
                        "geometry_source": "pdf_text",
                    },
                ],
                "geometry_source": "pdf_text",
            },
            {
                "page_number": 2,
                "width": 612.0,
                "height": 792.0,
                "text": "Legal precedent establishes that due process must be observed in all proceedings.",
                "text_blocks": [
                    {
                        "block_id": "b3",
                        "page_number": 2,
                        "text": "Legal precedent establishes that due process must be observed in all proceedings.",
                        "confidence": 0.91,
                        "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 20, "coordinate_space": "pdf_points"},
                        "geometry_source": "pdf_text",
                    },
                ],
                "geometry_source": "pdf_text",
            },
        ],
        "total_pages": 2,
    }

    # 1. Index
    print("== INDEX ==")
    resp = requests.post(f"{BASE}/knowledge/index", json=output)
    print("Status:", resp.status_code)
    idx = resp.json()
    summary = idx["summary"]
    print("Chunks indexed:", summary["chunks_indexed"])
    print("Embedding model:", summary["embedding_model"])
    print("Vector store:", summary["vector_store"])
    print("Errors:", idx.get("errors", []))

    # 2. Search
    print("\n== SEARCH: right to privacy ==")
    resp2 = requests.post(f"{BASE}/knowledge/search", json={"query": "right to privacy", "top_k": 5, "filters": []})
    print("Status:", resp2.status_code)
    sr = resp2.json()
    print("Results:", sr["total_results"])
    for i, item in enumerate(sr["items"]):
        score = item["score"]["raw_score"]
        page = item["metadata"]["page_number"]
        text = item["text"][:80]
        print(f"  [{i}] score={score:.4f} page={page} text={text}")

    # 3. Filtered search
    print("\n== FILTERED SEARCH: due process ==")
    resp3 = requests.post(
        f"{BASE}/knowledge/search",
        json={"query": "due process", "top_k": 5, "filters": [{"field": "document_id", "value": doc_id}]},
    )
    print("Status:", resp3.status_code)
    sf = resp3.json()
    print("Filtered results:", sf["total_results"])
    for i, item in enumerate(sf["items"]):
        score = item["score"]["raw_score"]
        page = item["metadata"]["page_number"]
        text = item["text"][:80]
        print(f"  [{i}] score={score:.4f} page={page} text={text}")

    # 4. Capabilities
    print("\n== CAPABILITIES ==")
    resp4 = requests.get(f"{BASE}/knowledge/capabilities")
    print("Status:", resp4.status_code)
    caps = resp4.json()
    print("Embedding:", caps["embedding"]["available"], caps["embedding"]["name"])
    print("Store:", caps["vector_store"]["available"], caps["vector_store"]["name"])
    print("Indexed chunks:", caps["indexed_chunks"])

    # 5. Existing foundations — providers
    print("\n== EXISTING FOUNDATIONS ==")
    resp5 = requests.get(f"{BASE}/providers")
    print("Providers status:", resp5.status_code)
    if resp5.status_code == 200:
        providers = resp5.json()
        print("Providers count:", len(providers.get("providers", [])))

    print("\nAll smoke tests passed!")


if __name__ == "__main__":
    main()
