# Security Policy

## Disclaimer

This project is provided as sample code accompanying an AWS Prescriptive Guidance pattern and is
NOT intended for production use without additional security hardening. See the "Production
Hardening Recommendations" section below.

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it by emailing
aws-security@amazon.com. Do not report security vulnerabilities through public GitHub issues.

## AWS Services Used

- Amazon S3 — Document storage (raw uploads, rendered pages, evidence archive)
- AWS Lambda — Pipeline orchestrator running Strands Agents
- Amazon Bedrock — LLM reasoning for agents (Claude Sonnet)
- Amazon Textract — OCR text extraction from contract PDFs
- Amazon DynamoDB — Hash store for duplicate detection
- Amazon EventBridge — Event routing for flagged documents
- Amazon SNS — Notification delivery to human reviewers
- Amazon CloudWatch — Logging, metrics dashboard, and alarms

## Prerequisites and Permissions

To deploy this solution, you need:

- An AWS account with permissions to create S3 buckets, Lambda functions, DynamoDB tables,
  EventBridge event buses, SNS topics, CloudWatch dashboards, and IAM roles
- Amazon Bedrock model access enabled for Claude Sonnet in your target region
- AWS CDK v2 and Python 3.11+

## Known Security Considerations

| Item | Category | Rationale |
|------|----------|-----------|
| Textract IAM uses Resource: "*" | Accepted Limitation | `textract:DetectDocumentText` does not support resource-level permissions (AWS API limitation) |
| SNS topic not KMS-encrypted | Security Debt | Notification content is document metadata (flagged status), not contract content |
| Lambda env vars use default encryption | Security Debt | Variables contain resource names/IDs, not secrets |
| S3 uses SSE-S3 (AES-256) not KMS | Accepted for Sample | KMS adds cost and complexity; SSE-S3 provides encryption at rest |
| DynamoDB full table scan for near-duplicates | Performance Consideration | Acceptable for sample workloads; production should use GSI or dedicated similarity search |

## Production Hardening Recommendations

Before using this code in a production environment:

- **IAM**: Scope Bedrock permissions to specific model ARNs; add condition keys for Textract
- **Encryption**: Upgrade S3 to SSE-KMS with customer-managed key; encrypt SNS topic; encrypt Lambda env vars with KMS
- **TLS**: Add DenyInsecureTransport bucket policy (enforces HTTPS-only access)
- **Networking**: Deploy Lambda in a VPC with VPC endpoints for S3, DynamoDB, Textract, Bedrock
- **Logging**: Enable S3 access logging; encrypt CloudWatch Logs with KMS; enable CloudTrail
- **Input validation**: Validate document_key format and file extension before processing
- **Rate limiting**: Add Lambda reserved concurrency and API Gateway throttling
- **DynamoDB**: Replace full table scan with a Global Secondary Index for pHash lookups
- **Monitoring**: Add GuardDuty, Security Hub, and Config rules for continuous compliance

## Resource Cleanup

To remove all resources deployed by this project:

1. `cdk destroy ContractPrecheckPipelineStack`
2. Manually empty and delete the S3 bucket: `aws s3 rb s3://<bucket-name> --force`
3. Manually delete the DynamoDB table: `aws dynamodb delete-table --table-name ContractHashes`

Note: S3 bucket and DynamoDB table use RETAIN removal policy and must be deleted manually.

## Dependencies

| Dependency | Version | Notes |
|------------|---------|-------|
| strands-agents | latest | Strands Agents SDK for agent orchestration |
| boto3 | >=1.34.0 | AWS SDK — no known vulnerabilities at pinned version |
| Pillow | >=10.0.0 | Image processing — keep updated for security patches |
| imagehash | >=4.3.0 | Perceptual hashing |
| aws-cdk-lib | >=2.150.0 | CDK infrastructure (dev dependency only) |