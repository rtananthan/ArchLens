from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration,
    Tags
)
from constructs import Construct
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tags import get_service_specific_tags, validate_tags

class StorageStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, environment: str = 'dev', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.deployment_env = environment
        
        # S3 bucket for file uploads
        self.upload_bucket = s3.Bucket(
            self, 'UploadBucket',
            bucket_name=f'archlens-uploads-{self.account}-{self.region}',
            versioned=False,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id='delete-incomplete-uploads',
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                    enabled=True
                ),
                s3.LifecycleRule(
                    id='delete-old-files',
                    expiration=Duration.days(2),  # Clean up files after 2 days
                    enabled=True
                )
            ],
            cors=[
                s3.CorsRule(
                    allowed_headers=['*'],
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.DELETE,
                        s3.HttpMethods.HEAD
                    ],
                    allowed_origins=['*'],  # Will be restricted in production
                    exposed_headers=['ETag']
                )
            ],
            removal_policy=RemovalPolicy.DESTROY  # For development
        )
        
        # Add specific tags for S3 bucket
        s3_tags = get_service_specific_tags(
            'Upload-Storage-Bucket', 
            'storage',
            {
                'DataType': 'User-Uploads',
                'RetentionPeriod': '48hours'
            }
        )
        
        for key, value in validate_tags(s3_tags).items():
            Tags.of(self.upload_bucket).add(key, value)
        
        # DynamoDB table for analysis results
        self.analysis_table = dynamodb.Table(
            self, 'AnalysisTable',
            table_name=f'ArchLens-Analysis-{self.region}',
            partition_key=dynamodb.Attribute(
                name='analysis_id',
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            time_to_live_attribute='ttl',  # Auto-cleanup after 48 hours
            removal_policy=RemovalPolicy.DESTROY,  # For development
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
        )
        
        # Add specific tags for DynamoDB table
        dynamodb_tags = get_service_specific_tags(
            'Analysis-Results-Table',
            'storage',
            {
                'DataType': 'Analysis-Results',
                'BillingMode': 'OnDemand'
            }
        )
        
        for key, value in validate_tags(dynamodb_tags).items():
            Tags.of(self.analysis_table).add(key, value)
        
        # GSI for querying by status
        self.analysis_table.add_global_secondary_index(
            index_name='status-timestamp-index',
            partition_key=dynamodb.Attribute(
                name='status',
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name='timestamp',
                type=dynamodb.AttributeType.STRING
            )
        )