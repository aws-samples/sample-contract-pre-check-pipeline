"""Amazon Bedrock multimodal watermark verification tools."""

import base64
import json
import logging

import boto3
from botocore.exceptions import ClientError
from strands import tool

from app.config import BUCKET_NAME, WATERMARK_REFS_PREFIX, BEDROCK_MODEL_ID, BEDROCK_REGION, WATERMARK_DETECTION_PROMPT

logger = logging.getLogger(__name__)

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


@tool
def load_watermark_references() -> dict:
    """Load reference watermark examples from S3 for few-shot prompting.

    Returns:
        A dict with reference examples (base64 images and metadata).
    """
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=WATERMARK_REFS_PREFIX)
    examples = []

    for obj in response.get("Contents", []):
        key = obj["Key"]
        if not key.endswith((".png", ".jpg", ".jpeg")):
            continue

        img_data = s3.get_object(Bucket=BUCKET_NAME, Key=key)["Body"].read()

        # Load corresponding metadata JSON if it exists
        meta_key = key.rsplit(".", 1)[0] + ".json"
        metadata = {}
        try:
            meta_resp = s3.get_object(Bucket=BUCKET_NAME, Key=meta_key)
            metadata = json.loads(meta_resp["Body"].read())
        except ClientError as err:
            # Missing sidecar metadata is expected; re-raise anything else.
            if err.response.get("Error", {}).get("Code") != "NoSuchKey":
                raise
            logger.debug("No metadata sidecar for %s", key)

        examples.append({
            "image_base64": base64.b64encode(img_data).decode("utf-8"),
            "metadata": metadata,
            "key": key,
        })

    return {"examples": examples, "count": len(examples)}


def _build_few_shot_prompt(reference_examples: list[dict]) -> str:
    """Build the few-shot section of the watermark prompt."""
    if not reference_examples:
        return ""
    parts = ["\nHere are reference watermark examples for comparison:\n"]
    for i, ex in enumerate(reference_examples, 1):
        meta = ex.get("metadata", {})
        parts.append(
            f"Example {i}: Type={meta.get('type', 'unknown')}, "
            f"Placement={meta.get('placement', 'unknown')}, "
            f"Integrity={meta.get('integrity', 'intact')}"
        )
    return "\n".join(parts)


@tool
def verify_watermark_on_page(
    page_image_bytes: bytes,
    reference_examples: list,
    page_number: int,
) -> dict:
    """Verify watermark on a single contract page using Bedrock multimodal model.

    Args:
        page_image_bytes: Raw PNG bytes of the page image.
        reference_examples: List of reference example dicts with image_base64 and metadata.
        page_number: The page number being analyzed.

    Returns:
        Watermark assessment dict with type, placement, integrity, confidence, explanation.
    """
    few_shot_section = _build_few_shot_prompt(reference_examples)
    full_prompt = WATERMARK_DETECTION_PROMPT + few_shot_section

    # Build message content: reference images first, then target image, then prompt
    message_content = []

    for ex in reference_examples:
        message_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": ex["image_base64"],
            },
        })

    message_content.append({
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(page_image_bytes).decode("utf-8"),
        },
    })
    message_content.append({"type": "text", "text": full_prompt})

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message_content}],
        }),
    )

    result = json.loads(response["body"].read())
    response_text = result["content"][0]["text"]

    try:
        finding = json.loads(response_text)
    except json.JSONDecodeError:
        finding = {
            "watermark_present": None,
            "watermark_type": "parse_error",
            "placement": "unknown",
            "integrity": "unknown",
            "confidence": "low",
            "explanation": f"Could not parse model response: {response_text[:200]}",
        }

    finding["page_number"] = page_number
    return finding
