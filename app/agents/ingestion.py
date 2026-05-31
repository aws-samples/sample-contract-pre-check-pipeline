"""Document Ingestion Agent — accepts contracts, renders pages, extracts text."""

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import BEDROCK_MODEL_ID, BEDROCK_REGION
from app.tools.s3_tools import download_from_s3, upload_to_s3
from app.tools.textract_tools import extract_text_with_textract, render_pdf_to_images

SYSTEM_PROMPT = """You are a document ingestion agent for a contract pre-check pipeline.

Your job is to process an uploaded contract document:
1. Download the contract from S3 using the provided key.
2. If the document is a PDF, render each page to a PNG image.
3. Extract text from the document using Amazon Textract.
4. Store rendered images and extracted text back in S3.

Return a JSON summary with:
- document_id: a unique identifier derived from the document key
- page_count: number of pages
- text_content: the full extracted text
- rendered_image_keys: list of S3 keys for rendered page images
- text_s3_key: S3 key where extracted text is stored
- agent_reasoning: explain what you did and any issues encountered

Always explain your reasoning clearly."""

from botocore.config import Config

_bedrock_config = Config(read_timeout=300, connect_timeout=10)
model = BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, boto_client_config=_bedrock_config)

ingestion_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[download_from_s3, upload_to_s3, extract_text_with_textract, render_pdf_to_images],
)
