"""Orchestration Agent — coordinates the full pre-check pipeline."""

import json
import logging
from datetime import datetime, timezone

from app.agents.ingestion import ingestion_agent
from app.agents.duplicate import duplicate_agent
from app.agents.watermark import watermark_agent
from app.report import build_precheck_report, archive_report
from app.tools.eventbridge_tools import publish_flagged_document

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def log_agent_decision(agent_name: str, document_key: str, decision: dict):
    """Log an agent decision in structured format for CloudWatch Logs Insights."""
    logger.info(json.dumps({
        "event_type": "agent_decision",
        "agent_name": agent_name,
        "document_key": document_key,
        "status": decision.get("overall_status", decision.get("status")),
        "confidence": decision.get("confidence"),
        "reasoning_summary": str(decision.get("agent_reasoning", ""))[:200],
    }))


def run_pipeline(document_key: str, bucket: str) -> dict:
    """Run the full contract pre-check pipeline.

    Args:
        document_key: S3 key of the uploaded contract.
        bucket: S3 bucket name.

    Returns:
        The complete pre-check report.
    """
    start_time = datetime.now(timezone.utc)
    logger.info(json.dumps({
        "event_type": "pipeline_start",
        "document_key": document_key,
        "bucket": bucket,
    }))

    # Step 1: Ingest document
    ingestion_result = ingestion_agent(
        f"Process the contract at s3://{bucket}/{document_key}. "
        f"The bucket is {bucket} and the key is {document_key}."
    )
    log_agent_decision("ingestion", document_key, {"status": "completed"})

    # Step 2: Duplicate detection
    duplicate_result = duplicate_agent(
        f"Check for duplicates. The extracted text content is: "
        f"{ingestion_result}. "
        f"The document key is {document_key}."
    )
    log_agent_decision("duplicate_detection", document_key, {
        "status": "completed",
        "confidence": "high",
    })

    # Step 3: Watermark verification
    watermark_result = watermark_agent(
        f"Verify watermarks on the rendered page images. "
        f"The ingestion result with image keys is: {ingestion_result}. "
        f"The bucket is {bucket}."
    )
    log_agent_decision("watermark_verification", document_key, {
        "status": "completed",
    })

    # Step 4: Build report
    # Parse agent outputs — Strands agents return AgentResult objects
    ingestion_dict = _parse_agent_result(ingestion_result)
    duplicate_dict = _parse_agent_result(duplicate_result)
    watermark_dict = _parse_agent_result(watermark_result)

    report = build_precheck_report(
        document_key=document_key,
        ingestion_result=ingestion_dict,
        duplicate_result=duplicate_dict,
        watermark_result=watermark_dict,
        start_time=start_time,
    )

    # Step 5: Archive report
    report_key = archive_report(report)
    report["report_s3_key"] = report_key

    # Step 6: Route flagged documents to human review
    if report["overall_status"] == "FLAGGED":
        publish_flagged_document(
            document_key=document_key,
            failure_reasons=report["failure_reasons"],
            overall_status=report["overall_status"],
            report_s3_key=report_key,
        )
        logger.info(json.dumps({
            "event_type": "document_flagged",
            "document_key": document_key,
            "failure_reasons": report["failure_reasons"],
        }))

    log_agent_decision("orchestrator", document_key, report)

    logger.info(json.dumps({
        "event_type": "pipeline_complete",
        "document_key": document_key,
        "overall_status": report["overall_status"],
        "duration_seconds": report["processing_duration_seconds"],
    }))

    return report


def _parse_agent_result(agent_result) -> dict:
    """Parse a Strands AgentResult into a dict.

    The agent returns an AgentResult object. We extract the text
    and attempt to parse it as JSON. Falls back to wrapping in a dict.
    """
    text = str(agent_result)
    try:
        # Try to find JSON in the response
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"raw_output": text}
