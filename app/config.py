"""Configuration and constants for the contract pre-check pipeline."""

import os

# S3
BUCKET_NAME = os.environ.get("BUCKET_NAME", "contract-precheck-bucket")
RAW_PREFIX = "raw/"
RENDERED_PREFIX = "rendered/"
EXTRACTED_TEXT_PREFIX = "extracted-text/"
WATERMARK_REFS_PREFIX = "watermark-references/"
EVIDENCE_PREFIX = "evidence/"
REPORTS_PREFIX = "evidence/reports/"

# DynamoDB
HASH_TABLE_NAME = os.environ.get("HASH_TABLE_NAME", "ContractHashes")

# Bedrock
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-opus-4-20250514-v1:0"
)
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")

# EventBridge
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "contract-precheck-bus")
EVENT_SOURCE = "contract-precheck-pipeline"

# Duplicate detection thresholds
HAMMING_DISTANCE_THRESHOLD = int(os.environ.get("HAMMING_THRESHOLD", "10"))
NEAR_DUPLICATE_SIMILARITY_THRESHOLD = float(
    os.environ.get("SIMILARITY_THRESHOLD", "85.0")
)

# Watermark detection prompt
WATERMARK_DETECTION_PROMPT = """Analyze the provided contract page image for watermarks.

Identify and report on the following:
1. Watermark presence: Is a watermark visible on this page? (yes/no)
2. Watermark type: Classify as one of: corporate_logo, draft_stamp, confidential_overlay, digital_signature_seal, other, none
3. Watermark placement: Describe the location (center, top-left, bottom-right, diagonal, full-page, etc.)
4. Watermark integrity: Assess whether the watermark appears authentic and unaltered (intact, degraded, suspicious, not_applicable)
5. Confidence: Rate your confidence in this assessment (high, medium, low)
6. Explanation: Provide a brief natural language explanation of your finding.

Respond in the following JSON format only:
{
    "watermark_present": true/false,
    "watermark_type": "string",
    "placement": "string",
    "integrity": "string",
    "confidence": "string",
    "explanation": "string"
}"""
