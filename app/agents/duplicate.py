"""Duplicate Detection Agent — hash-based exact and near-duplicate detection."""

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import BEDROCK_MODEL_ID, BEDROCK_REGION
from app.tools.hash_tools import compute_sha256_hash, compute_perceptual_hash
from app.tools.dynamodb_tools import query_exact_duplicate, find_near_duplicates, store_document_hashes

SYSTEM_PROMPT = """You are a duplicate detection agent for a contract pre-check pipeline.

Your job is to detect duplicate and near-duplicate contract submissions:
1. Compute the SHA-256 hash of the document's extracted text content.
2. Query DynamoDB for an exact match using the SHA-256 hash.
3. Compute perceptual hashes (pHash) for each rendered page image.
4. Search for near-duplicates by comparing pHash values using Hamming distance.
5. Store the new document's hashes in DynamoDB for future lookups.

Return a JSON result with:
- sha256_hash: the computed SHA-256 hash
- is_exact_duplicate: true/false
- exact_match_details: details of the matching document if exact duplicate found
- near_duplicates: list of near-duplicate matches with similarity scores
- agent_reasoning: explain your findings and why you flagged or cleared the document
- confidence: high/medium/low

Always explain your reasoning clearly."""

from botocore.config import Config
_bedrock_config = Config(read_timeout=300, connect_timeout=10)
model = BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, boto_client_config=_bedrock_config)

duplicate_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        compute_sha256_hash,
        compute_perceptual_hash,
        query_exact_duplicate,
        find_near_duplicates,
        store_document_hashes,
    ],
)
