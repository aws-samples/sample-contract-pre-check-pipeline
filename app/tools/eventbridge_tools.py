"""Amazon EventBridge routing tools for human review."""

import json

import boto3
from strands import tool

from app.config import EVENT_BUS_NAME, EVENT_SOURCE

events = boto3.client("events")


@tool
def publish_flagged_document(
    document_key: str,
    failure_reasons: list,
    overall_status: str,
    report_s3_key: str,
) -> dict:
    """Publish a flagged document event to EventBridge for human review.

    Args:
        document_key: S3 key of the flagged contract.
        failure_reasons: List of reasons the document was flagged.
        overall_status: The overall pre-check status (FLAGGED).
        report_s3_key: S3 key where the full report is archived.

    Returns:
        Confirmation with the EventBridge event ID.
    """
    response = events.put_events(
        Entries=[
            {
                "Source": EVENT_SOURCE,
                "DetailType": "ContractFlagged",
                "Detail": json.dumps({
                    "document_key": document_key,
                    "failure_reasons": failure_reasons,
                    "overall_status": overall_status,
                    "report_location": report_s3_key,
                }),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )
    return {
        "event_id": response["Entries"][0]["EventId"],
        "status": "published",
    }
