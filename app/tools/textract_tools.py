"""Amazon Textract text extraction tools."""

import io
import logging
import tempfile
from pathlib import Path

import boto3
from strands import tool

from app.config import BUCKET_NAME, RENDERED_PREFIX, EXTRACTED_TEXT_PREFIX

logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.info("pdf2image not available; render_pdf_to_images will skip rendering")

s3 = boto3.client("s3")
textract = boto3.client("textract")


@tool
def extract_text_with_textract(bucket: str, key: str, use_analyze: bool = False) -> dict:
    """Extract text from a document stored in S3 using Amazon Textract.

    Args:
        bucket: S3 bucket name.
        key: S3 object key of the document.
        use_analyze: If True, use AnalyzeDocument for tables/forms. Otherwise use DetectDocumentText.

    Returns:
        A dict with extracted text and line count.
    """
    document = {"S3Object": {"Bucket": bucket, "Name": key}}

    if use_analyze:
        response = textract.analyze_document(
            Document=document, FeatureTypes=["TABLES", "FORMS"]
        )
    else:
        response = textract.detect_document_text(Document=document)

    blocks = response.get("Blocks", [])
    lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
    text_content = "\n".join(lines)

    return {"text_content": text_content, "line_count": len(lines)}


@tool
def render_pdf_to_images(pdf_bytes: bytes, document_id: str) -> dict:
    """Render PDF pages to PNG images and upload to S3.

    Args:
        pdf_bytes: The raw PDF file content.
        document_id: Unique identifier for the document (used in S3 keys).

    Returns:
        A dict with rendered image S3 keys and page count.
    """
    if not PDF2IMAGE_AVAILABLE:
        return {
            "image_keys": [],
            "page_count": 0,
            "note": "pdf2image/poppler not available; skipping page rendering",
        }

    images = convert_from_bytes(pdf_bytes, dpi=200, fmt="png")
    image_keys = []

    for i, img in enumerate(images, 1):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        key = f"{RENDERED_PREFIX}{document_id}-page-{i}.png"
        s3.put_object(
            Bucket=BUCKET_NAME, Key=key, Body=buf.read(), ContentType="image/png"
        )
        image_keys.append(key)

    return {"image_keys": image_keys, "page_count": len(images)}
