# Contract Pre-Check Pipeline 

Automated contract pre-check pipeline using [Strands Agents SDK](https://github.com/strands-agents/sdk-python), Amazon Bedrock, Amazon Textract, and hash-based duplicate detection.

## Architecture

![Architecture Overview](Architecture%20Diagrams/architecture-overview.png)

The pipeline processes uploaded contract PDFs through three sequential AI agents, each powered by Amazon Bedrock Claude Sonnet, to validate document integrity before human review.

**AWS Services Used:**

| Service | Purpose |
|---------|---------|
| Amazon S3 | Document storage (raw uploads, rendered pages, evidence archive) |
| AWS Lambda | Pipeline orchestrator running Strands Agents |
| Amazon Bedrock | LLM reasoning for agents (Claude Sonnet) |
| Amazon Textract | OCR text extraction from contract PDFs |
| Amazon DynamoDB | Hash store for duplicate detection |
| Amazon EventBridge | Event routing for flagged documents |
| Amazon SNS | Notification delivery to human reviewers |
| Amazon CloudWatch | Logging, metrics dashboard, and alarms |

## Agent Pipeline

![Agent Pipeline](Architecture%20Diagrams/agent-pipeline.png)

Three agents execute sequentially within a single Lambda invocation:

1. **Ingestion Agent** — Downloads the PDF from S3, renders pages to PNG, and extracts text via Textract.
2. **Duplicate Detection Agent** — Computes SHA-256 (exact match) and perceptual hashes (near-duplicate) against DynamoDB.
3. **Watermark Verification Agent** — Uses Bedrock multimodal few-shot prompting to assess watermark presence and integrity.

Results are combined into a pre-check report. Documents are either **PASSED** (archived to S3) or **FLAGGED** (routed to EventBridge → SNS for human review).

## Duplicate Detection

![Duplicate Detection Flow](Architecture%20Diagrams/duplicate-detection-flow.png)

Two-tier detection:

- **Exact match** — SHA-256 hash of extracted text queried against DynamoDB.
- **Near-duplicate** — Perceptual hash (pHash) per page image, compared via Hamming distance (threshold: ≤10 bits, ~85% similarity).

New documents have their hashes stored for future comparisons.

## Watermark Verification

![Watermark Verification](Architecture%20Diagrams/watermark-verification.png)

The watermark agent sends each page image to Bedrock Claude alongside reference watermark examples (few-shot). The model assesses:

- Watermark presence (yes/no)
- Type (corporate logo, draft stamp, confidential overlay)
- Placement and integrity
- Confidence level

A page is flagged if confidence is low, the watermark is missing on page 1, or integrity appears suspicious.

## Project Structure

```
solution/
├── app/                          # Application code
│   ├── agents/                   # Strands Agent definitions
│   │   ├── ingestion.py          # Document Ingestion Agent
│   │   ├── duplicate.py          # Duplicate Detection Agent
│   │   ├── watermark.py          # Watermark Verification Agent
│   │   └── orchestrator.py       # Orchestration logic
│   ├── tools/                    # Agent tools
│   │   ├── s3_tools.py           # S3 upload/download
│   │   ├── textract_tools.py     # Textract extraction + PDF rendering
│   │   ├── hash_tools.py         # SHA-256 + pHash computation
│   │   ├── dynamodb_tools.py     # DynamoDB hash storage/lookup
│   │   ├── bedrock_tools.py      # Bedrock multimodal watermark analysis
│   │   └── eventbridge_tools.py  # EventBridge routing
│   ├── config.py                 # Configuration and constants
│   ├── report.py                 # Pre-check report builder
│   └── handler.py                # Lambda entry point
├── infra/                        # CDK infrastructure
│   ├── app.py                    # CDK app entry point
│   └── stacks/
│       └── pipeline_stack.py     # Main infrastructure stack
├── Architecture Diagrams/        # Architecture diagrams (PNG)
├── sample_contracts/             # Sample contract PDFs for testing
├── requirements.txt              # Python runtime dependencies
└── requirements-dev.txt          # CDK dependencies
```

## Prerequisites

- Python 3.11+
- AWS CLI v2 configured
- AWS CDK v2 (`npm install -g aws-cdk`)
- Amazon Bedrock model access enabled (Claude Sonnet)

## Deploy

```bash
cd solution

# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy infrastructure
cdk deploy ContractPrecheckPipelineStack
```

## Test

Upload a sample contract PDF to the S3 bucket `raw/` prefix:

```bash
# Get bucket name from stack outputs
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ContractPrecheckPipelineStack \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text)

# Upload a sample contract
aws s3 cp sample_contracts/OnePageContract.pdf "s3://${BUCKET}/raw/OnePageContract.pdf"
```

The S3 event notification triggers the Lambda automatically. Check results in CloudWatch Logs or the `evidence/reports/` prefix in S3.

## Configuration

Environment variables (set automatically by CDK):

| Variable | Default | Description |
|----------|---------|-------------|
| `BUCKET_NAME` | *(from CDK)* | S3 bucket for document storage |
| `HASH_TABLE_NAME` | `ContractHashes` | DynamoDB table for hash lookups |
| `EVENT_BUS_NAME` | `contract-precheck-bus` | EventBridge bus for flagged documents |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-*` | Bedrock model for agent reasoning |
| `BEDROCK_REGION` | `us-east-1` | Region for Bedrock API calls |
| `HAMMING_THRESHOLD` | `10` | Max Hamming distance for near-duplicates |
| `SIMILARITY_THRESHOLD` | `85.0` | Min similarity % to flag near-duplicates |

## Cleanup

```bash
cdk destroy ContractPrecheckPipelineStack
```

Note: The S3 bucket and DynamoDB table use `RETAIN` removal policy. Delete them manually if needed:

```bash
aws s3 rb s3://<bucket-name> --force
aws dynamodb delete-table --table-name ContractHashes
```

## Security

- S3 bucket: versioning enabled, public access blocked, server-side encryption (AES-256)
- DynamoDB: encryption at rest (AWS-managed), point-in-time recovery enabled
- Lambda: least-privilege IAM role scoped to specific resources
- No secrets in code — all configuration via environment variables

## License

This sample is licensed under the MIT-0 License. See the LICENSE file.
