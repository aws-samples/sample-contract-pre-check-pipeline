#!/usr/bin/env python3
"""CDK app entry point for the contract pre-check pipeline."""

import aws_cdk as cdk

from stacks.pipeline_stack import ContractPrecheckPipelineStack

app = cdk.App()

ContractPrecheckPipelineStack(
    app,
    "ContractPrecheckPipelineStack",
    description="Automated contract pre-check pipeline with Strands Agents, "
    "Bedrock multimodal watermark verification, and hash-based duplicate detection.",
)

app.synth()
