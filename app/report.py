"""Pre-check report builder and pass/fail logic."""

import json
import uuid
from datetime import datetime, timezone

import boto3

from app.config import (
    BUCKET_NAME,
    REPORTS_PREFIX,
    NEAR_DUPLICATE_SIMILARITY_THRESHOLD,
)

s3 = boto3.client("s3")


def determine_status(duplicate_result: dict, watermark_result: dict) -> tuple[str, list[str]]:
    """Determine overall pre-check status based on agent results.

    Returns:
        A tuple of (status, failure_reasons).
    """
    failure_reasons = []

    # Check for exact duplicates
    if duplicate_result.get("is_exact_duplicate"):
        failure_reasons.append("exact_duplicate_detected")

    # Check for near-duplicates
    near_dupes = duplicate_result.get("near_duplicates", [])
    if any(nd["similarity"] > NEAR_DUPLICATE_SIMILARITY_THRESHOLD for nd in near_dupes):
        failure_reasons.append("near_duplicate_detected")

    # Check watermark findings
    pages = watermark_result.get("pages", [])
    for page in pages:
        if page.get("confidence") == "low":
            failure_reasons.append("watermark_low_confidence")
            break
        if page.get("watermark_present") is False and page.get("page_number") == 1:
            failure_reasons.append("missing_watermark_page_1")
            break
        if page.get("integrity") == "suspicious":
            failure_reasons.append("suspicious_watermark")
            break

    status = "FLAGGED" if failure_reasons else "PASSED"
    return status, failure_reasons


def build_precheck_report(
    document_key: str,
    ingestion_result: dict,
    duplicate_result: dict,
    watermark_result: dict,
    start_time: datetime,
) -> dict:
    """Build the unified JSON pre-check report.

    Args:
        document_key: S3 key of the original contract.
        ingestion_result: Output from the Ingestion Agent.
        duplicate_result: Output from the Duplicate Detection Agent.
        watermark_result: Output from the Watermark Verification Agent.
        start_time: Pipeline start timestamp.

    Returns:
        The complete pre-check report dict.
    """
    end_time = datetime.now(timezone.utc)
    status, failure_reasons = determine_status(duplicate_result, watermark_result)

    report = {
        "report_id": f"rpt-{end_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}",
        "document_key": document_key,
        "submitted_at": start_time.isoformat(),
        "processed_at": end_time.isoformat(),
        "processing_duration_seconds": round((end_time - start_time).total_seconds(), 1),
        "overall_status": status,
        "failure_reasons": failure_reasons,
        "ingestion": ingestion_result,
        "duplicate_detection": duplicate_result,
        "watermark_verification": watermark_result,
    }

    return report


def archive_report(report: dict) -> str:
    """Archive the pre-check report to S3.

    Args:
        report: The complete pre-check report.

    Returns:
        The S3 key where the report was archived.
    """
    report_key = f"{REPORTS_PREFIX}{report['report_id']}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=report_key,
        Body=json.dumps(report, indent=2, default=str),
        ContentType="application/json",
    )
    return report_key
