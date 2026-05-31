"""Watermark Verification Agent — multimodal Bedrock watermark analysis."""

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import BEDROCK_MODEL_ID, BEDROCK_REGION
from app.tools.bedrock_tools import load_watermark_references, verify_watermark_on_page
from app.tools.s3_tools import download_from_s3

SYSTEM_PROMPT = """You are a watermark verification agent for a contract pre-check pipeline.

Your job is to verify watermarks on contract page images:
1. Load reference watermark examples from S3 for few-shot comparison.
2. For each rendered page image, download it from S3.
3. Send each page image to the Bedrock multimodal model for watermark analysis.
4. Collect per-page findings: watermark presence, type, placement, integrity, confidence.

Return a JSON result with:
- pages: list of per-page watermark findings
- agent_reasoning: summarize your overall assessment across all pages
- confidence: overall confidence (high/medium/low) based on the lowest per-page confidence

Flag any page with low confidence or suspicious integrity for human review.
Always explain your reasoning clearly."""

from botocore.config import Config
_bedrock_config = Config(read_timeout=300, connect_timeout=10)
model = BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, boto_client_config=_bedrock_config)

watermark_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[load_watermark_references, verify_watermark_on_page, download_from_s3],
)
