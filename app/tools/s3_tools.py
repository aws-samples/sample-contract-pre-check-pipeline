"""S3 upload and download tools for the contract pre-check pipeline."""

import io
import boto3
from strands import tool

from app.config import BUCKET_NAME

s3 = boto3.client("s3")


@tool
def download_from_s3(key: str) -> dict:
    """Download a file from S3.

    Args:
        key: The S3 object key to download.

    Returns:
        A dict with the file bytes and content type.
    """
    response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    body = response["Body"].read()
    return {
        "body": body,
        "content_type": response.get("ContentType", "application/octet-stream"),
        "key": key,
    }


@tool
def upload_to_s3(key: str, body: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload a file to S3.

    Args:
        key: The S3 object key.
        body: The file content as bytes.
        content_type: The MIME content type.

    Returns:
        Confirmation with the uploaded key.
    """
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=body, ContentType=content_type)
    return {"key": key, "bucket": BUCKET_NAME, "status": "uploaded"}


@tool
def list_s3_objects(prefix: str) -> dict:
    """List objects in S3 under a given prefix.

    Args:
        prefix: The S3 prefix to list.

    Returns:
        A dict with the list of object keys.
    """
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    keys = [obj["Key"] for obj in response.get("Contents", [])]
    return {"keys": keys, "count": len(keys)}
