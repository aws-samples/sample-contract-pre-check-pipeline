"""DynamoDB hash storage and lookup tools."""

from datetime import datetime, timezone

import boto3
from strands import tool

from app.config import HASH_TABLE_NAME, HAMMING_DISTANCE_THRESHOLD
from app.tools.hash_tools import hamming_distance

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(HASH_TABLE_NAME)


@tool
def query_exact_duplicate(sha256_hash: str) -> dict:
    """Query DynamoDB for an exact-match duplicate by SHA-256 hash.

    Args:
        sha256_hash: The SHA-256 hash to look up.

    Returns:
        A dict with is_duplicate flag and matching document details if found.
    """
    response = table.query(
        KeyConditionExpression="sha256_hash = :h",
        ExpressionAttributeValues={":h": sha256_hash},
        Limit=1,
    )
    items = response.get("Items", [])

    if items:
        item = items[0]
        return {
            "is_duplicate": True,
            "matching_document_id": item["document_id"],
            "matching_document_key": item["document_key"],
            "submitted_at": item["submitted_at"],
        }
    return {"is_duplicate": False}


@tool
def find_near_duplicates(phash_values: list, threshold: int = None) -> dict:
    """Scan DynamoDB for near-duplicate documents using pHash Hamming distance.

    Args:
        phash_values: List of pHash hex strings for the new document pages.
        threshold: Hamming distance threshold. Defaults to config value.

    Returns:
        A dict with near_duplicate matches and their similarity scores.
    """
    if threshold is None:
        threshold = HAMMING_DISTANCE_THRESHOLD

    # Scan all stored hashes
    scan_response = table.scan(
        ProjectionExpression="document_id, document_key, phash_values, submitted_at"
    )
    stored_records = scan_response.get("Items", [])

    matches = []
    seen_docs = set()

    for new_phash in phash_values:
        for record in stored_records:
            doc_id = record["document_id"]
            if doc_id in seen_docs:
                continue
            stored_phashes = record.get("phash_values", [])
            for stored_phash in stored_phashes:
                dist = hamming_distance(new_phash, stored_phash)
                if dist <= threshold:
                    similarity = round((1 - dist / 64) * 100, 1)
                    matches.append({
                        "document_id": doc_id,
                        "document_key": record["document_key"],
                        "hamming_distance": dist,
                        "similarity": similarity,
                    })
                    seen_docs.add(doc_id)
                    break

    return {"near_duplicates": matches, "count": len(matches)}


@tool
def store_document_hashes(
    sha256_hash: str,
    document_id: str,
    document_key: str,
    phash_values: list,
    page_count: int,
    submitter_id: str = "system",
) -> dict:
    """Store document hashes in DynamoDB.

    Args:
        sha256_hash: SHA-256 hash of the document text.
        document_id: Unique document identifier.
        document_key: S3 key of the original document.
        phash_values: List of pHash hex strings (one per page).
        page_count: Number of pages in the document.
        submitter_id: Identifier of who submitted the document.

    Returns:
        Confirmation of storage.
    """
    table.put_item(
        Item={
            "sha256_hash": sha256_hash,
            "document_id": document_id,
            "document_key": document_key,
            "phash_values": phash_values,
            "page_count": page_count,
            "submitter_id": submitter_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"status": "stored", "document_id": document_id}
