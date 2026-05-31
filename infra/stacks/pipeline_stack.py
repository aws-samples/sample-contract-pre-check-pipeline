"""CDK stack for the contract pre-check pipeline infrastructure."""

import os
from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_s3_notifications as s3n,
)
from constructs import Construct


class ContractPrecheckPipelineStack(Stack):
    """Infrastructure stack for the contract pre-check pipeline."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------
        # S3 Bucket — document storage and evidence archive
        # -------------------------------------------------------
        bucket = s3.Bucket(
            self,
            "ContractBucket",
            bucket_name=None,
            versioned=True,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveEvidence",
                    prefix="evidence/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                ),
            ],
        )

        # -------------------------------------------------------
        # DynamoDB Table — hash storage for duplicate detection
        # -------------------------------------------------------
        hash_table = dynamodb.Table(
            self,
            "ContractHashesTable",
            table_name="ContractHashes",
            partition_key=dynamodb.Attribute(
                name="sha256_hash", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="document_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True,
            ),
        )

        # -------------------------------------------------------
        # EventBridge — custom event bus for human review routing
        # -------------------------------------------------------
        event_bus = events.EventBus(
            self,
            "ContractPrecheckBus",
            event_bus_name="contract-precheck-bus",
        )

        # SNS topic for review notifications
        review_topic = sns.Topic(
            self,
            "ReviewNotificationTopic",
            topic_name="contract-precheck-review",
        )

        # EventBridge rule: route flagged documents to SNS
        events.Rule(
            self,
            "FlaggedDocumentRule",
            event_bus=event_bus,
            event_pattern=events.EventPattern(
                source=["contract-precheck-pipeline"],
                detail_type=["ContractFlagged"],
            ),
            targets=[targets.SnsTopic(review_topic)],
        )

        # -------------------------------------------------------
        # Lambda — zip-based Python function with dependencies layer
        # -------------------------------------------------------
        app_dir = str(Path(__file__).resolve().parent.parent.parent)

        deps_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "DepsLayer",
            f"arn:aws:lambda:{self.region}:{self.account}:layer:contract-precheck-deps:2",
        )

        pipeline_function = lambda_.Function(
            self,
            "PipelineFunction",
            function_name="contract-precheck-pipeline",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="app.handler.lambda_handler",
            code=lambda_.Code.from_asset(
                app_dir,
                exclude=[
                    ".venv",
                    "infra",
                    "cdk.out",
                    "ash-output",
                    "*.pdf",
                    ".DS_Store",
                    "__pycache__",
                    "*.pyc",
                    "requirements-dev.txt",
                    "Dockerfile",
                    "README.md",
                    "cdk.json",
                ],
            ),
            layers=[deps_layer],
            memory_size=1024,
            timeout=Duration.minutes(5),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "HASH_TABLE_NAME": hash_table.table_name,
                "EVENT_BUS_NAME": event_bus.event_bus_name,
                "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "BEDROCK_REGION": self.region,
                "HAMMING_THRESHOLD": "10",
                "SIMILARITY_THRESHOLD": "85.0",
                "OTEL_PYTHON_CONTEXT": "contextvars_context",
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # -------------------------------------------------------
        # IAM permissions
        # -------------------------------------------------------
        bucket.grant_read_write(pipeline_function)
        hash_table.grant_read_write_data(pipeline_function)
        event_bus.grant_put_events_to(pipeline_function)

        # Textract permissions
        pipeline_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "textract:DetectDocumentText",
                    "textract:AnalyzeDocument",
                ],
                resources=["*"],
            )
        )

        # Bedrock permissions — scoped to the specific inference profile and foundation model
        bedrock_model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"
        pipeline_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/{bedrock_model_id}",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.{bedrock_model_id}",
                ],
            )
        )

        # -------------------------------------------------------
        # S3 event notification — trigger pipeline on upload to raw/
        # -------------------------------------------------------
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(pipeline_function),
            s3.NotificationKeyFilter(prefix="raw/"),
        )

        # -------------------------------------------------------
        # CloudWatch Dashboard
        # -------------------------------------------------------
        dashboard = cloudwatch.Dashboard(
            self,
            "PipelineDashboard",
            dashboard_name="ContractPrecheckPipeline",
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations",
                left=[pipeline_function.metric_invocations()],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Errors",
                left=[pipeline_function.metric_errors()],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Duration",
                left=[pipeline_function.metric_duration()],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="DynamoDB Read/Write Capacity",
                left=[
                    hash_table.metric_consumed_read_capacity_units(),
                    hash_table.metric_consumed_write_capacity_units(),
                ],
                width=12,
            ),
        )

        # CloudWatch Alarms
        pipeline_function.metric_errors().create_alarm(
            self,
            "PipelineErrorAlarm",
            alarm_name="ContractPipeline-HighErrorRate",
            threshold=5,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        pipeline_function.metric_duration().create_alarm(
            self,
            "PipelineLatencyAlarm",
            alarm_name="ContractPipeline-HighLatency",
            threshold=240_000,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        # -------------------------------------------------------
        # Outputs
        # -------------------------------------------------------
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "HashTableName", value=hash_table.table_name)
        CfnOutput(self, "EventBusName", value=event_bus.event_bus_name)
        CfnOutput(self, "ReviewTopicArn", value=review_topic.topic_arn)
        CfnOutput(self, "PipelineFunctionName", value=pipeline_function.function_name)
        CfnOutput(self, "DashboardName", value=dashboard.dashboard_name)
