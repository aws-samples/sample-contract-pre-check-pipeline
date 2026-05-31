"""Lambda entry point for the contract pre-check pipeline."""

import json
import logging
import urllib.parse

from app.agents.orchestrator import run_pipeline
from app.config import BUCKET_NAME

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Handle S3 event notifications or direct invocations.

    Supports two trigger modes:
    1. S3 event notification — triggered when a contract is uploaded to raw/
    2. Direct invocation — pass {"document_key": "raw/file.pdf", "bucket": "bucket-name"}
    """
    logger.info(json.dumps({"event_type": "lambda_invocation", "event": event}))

    # Determine document_key and bucket from event
    if "Records" in event:
        # S3 event notification
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        document_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    else:
        # Direct invocation
        document_key = event["document_key"]
        bucket = event.get("bucket", BUCKET_NAME)

    logger.info(json.dumps({
        "event_type": "processing_document",
        "document_key": document_key,
        "bucket": bucket,
    }))

    report = run_pipeline(document_key=document_key, bucket=bucket)

    return {
        "statusCode": 200,
        "body": json.dumps(report, default=str),
    }
