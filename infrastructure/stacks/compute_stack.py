# ArchLens Infrastructure - Compute Stack
# This CDK stack defines the serverless compute layer for ArchLens.
# It creates Lambda functions, API Gateway, and IAM roles for the backend processing.

# AWS CDK imports for infrastructure components
from aws_cdk import (
    Stack,                           # Base stack class
    aws_lambda as _lambda,           # Lambda functions for serverless compute
    aws_apigateway as apigateway,    # REST API for frontend-backend communication
    aws_iam as iam,                  # Identity and Access Management for security
    Duration,                        # Time duration utilities
    Tags,                           # Resource tagging for cost allocation
    BundlingOptions                 # Lambda deployment packaging options
)
from constructs import Construct    # CDK construct base class

# Python path manipulation to import custom configuration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tags import get_service_specific_tags, validate_tags  # Custom tagging utilities

class ComputeStack(Stack):
    """
    Compute Stack - Serverless backend processing layer.
    
    This stack creates the compute infrastructure for ArchLens:
    - Lambda functions for API handling and background processing
    - API Gateway for REST API endpoints
    - IAM roles with least-privilege permissions
    - Integration with Storage and AI stacks
    
    Dependencies:
    - StorageStack: Provides S3 bucket and DynamoDB table references
    - AIStack: Provides Bedrock agent ID for AI analysis
    """
    
    def __init__(self, scope: Construct, construct_id: str, storage_stack, ai_stack, environment: str = 'dev', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Store references to dependent stacks for resource access
        self.storage_stack = storage_stack  # For S3 bucket and DynamoDB table ARNs
        self.ai_stack = ai_stack           # For Bedrock agent ID
        self.deployment_env = environment   # Environment tag (dev/staging/prod)
        
        # Step 1: Create IAM role for Lambda functions
        # This role defines what AWS services the Lambda functions can access
        lambda_role = iam.Role(
            self, 'LambdaExecutionRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),  # Allow Lambda service to assume this role
            managed_policies=[
                # AWS-managed policy for basic Lambda logging to CloudWatch
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ],
            # Custom inline policy with specific permissions for ArchLens functionality
            inline_policies={
                'ArchLensLambdaPolicy': iam.PolicyDocument(
                    statements=[
                        # S3 permissions - for file storage and retrieval
                        # Lambda functions need to store uploaded files and read them for processing
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                's3:GetObject',    # Read uploaded files
                                's3:PutObject',    # Store new files
                                's3:DeleteObject'  # Clean up temporary files
                            ],
                            resources=[
                                f'{storage_stack.upload_bucket.bucket_arn}/*'  # Only access files in upload bucket
                            ]
                        ),
                        # DynamoDB permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'dynamodb:GetItem',
                                'dynamodb:PutItem',
                                'dynamodb:UpdateItem',
                                'dynamodb:DeleteItem',
                                'dynamodb:Query',
                                'dynamodb:Scan'
                            ],
                            resources=[
                                storage_stack.analysis_table.table_arn,
                                f'{storage_stack.analysis_table.table_arn}/index/*'
                            ]
                        ),
                        # Bedrock permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'bedrock:InvokeAgent',
                                'bedrock-agent-runtime:InvokeAgent',
                                'bedrock-runtime:InvokeModel'
                            ],
                            resources=[
                                f'arn:aws:bedrock:{self.region}:{self.account}:agent/*',
                                f'arn:aws:bedrock:{self.region}:{self.account}:agent-alias/*/*',
                                f'arn:aws:bedrock:{self.region}::foundation-model/*'
                            ]
                        ),
                        # Lambda invoke permissions for async calls
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'lambda:InvokeFunction'
                            ],
                            resources=[
                                f'arn:aws:lambda:{self.region}:{self.account}:function:*'
                            ]
                        )
                    ]
                )
            }
        )
        
        # Add tags for Lambda execution role
        lambda_role_tags = get_service_specific_tags(
            'Lambda-Execution-Role',
            'compute',
            {
                'IAMResourceType': 'Service-Role',
                'PermissionScope': 'Multi-Service'
            }
        )
        
        for key, value in validate_tags(lambda_role_tags).items():
            Tags.of(lambda_role).add(key, value)
        
        # Main API Lambda function (using simpler handler for now)
        self.api_lambda = _lambda.Function(
            self, 'APILambda',
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler='lightweight_handler.handler',
            code=_lambda.Code.from_asset('../backend_clean'),
            role=lambda_role,
            timeout=Duration.seconds(900),  # 15 minutes for analysis
            memory_size=1024,
            environment={
                'UPLOAD_BUCKET': storage_stack.upload_bucket.bucket_name,
                'ANALYSIS_TABLE': storage_stack.analysis_table.table_name,
                'BEDROCK_AGENT_ID': ai_stack.security_analysis_agent.attr_agent_id,
                'BEDROCK_AGENT_ALIAS_ID': 'TSTALIASID'  # Default test alias
            }
        )
        
        # Add tags for API Lambda function
        api_lambda_tags = get_service_specific_tags(
            'API-Lambda-Function',
            'compute',
            {
                'Runtime': 'Python-3.11',
                'LambdaType': 'API-Handler'
            }
        )
        
        for key, value in validate_tags(api_lambda_tags).items():
            Tags.of(self.api_lambda).add(key, value)
        
        # Analysis processor Lambda (for async processing)
        self.processor_lambda = _lambda.Function(
            self, 'ProcessorLambda',
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler='lightweight_processor.handler',
            code=_lambda.Code.from_asset('../backend_clean'),
            role=lambda_role,
            timeout=Duration.seconds(900),
            memory_size=2048,  # More memory for XML processing and AI calls
            environment={
                'UPLOAD_BUCKET': storage_stack.upload_bucket.bucket_name,
                'ANALYSIS_TABLE': storage_stack.analysis_table.table_name,
                'BEDROCK_AGENT_ID': ai_stack.security_analysis_agent.attr_agent_id,
                'BEDROCK_AGENT_ALIAS_ID': 'TSTALIASID'
            }
        )
        
        # Add tags for Processor Lambda function
        processor_lambda_tags = get_service_specific_tags(
            'Processor-Lambda-Function',
            'compute',
            {
                'Runtime': 'Python-3.11',
                'LambdaType': 'Background-Processor'
            }
        )
        
        for key, value in validate_tags(processor_lambda_tags).items():
            Tags.of(self.processor_lambda).add(key, value)
        
        # API Gateway
        self.api_gateway = apigateway.RestApi(
            self, 'ArchLensAPI',
            rest_api_name='ArchLens API',
            description='ArchLens AWS Architecture Analysis API',
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token']
            ),
            binary_media_types=['multipart/form-data', 'application/octet-stream'],
            deploy_options=apigateway.StageOptions(
                stage_name='prod',
                throttling_rate_limit=100,
                throttling_burst_limit=200
            )
        )
        
        # Add tags for API Gateway
        api_gateway_tags = get_service_specific_tags(
            'REST-API-Gateway',
            'networking',
            {
                'APIType': 'REST-API',
                'ThrottlingEnabled': 'true'
            }
        )
        
        for key, value in validate_tags(api_gateway_tags).items():
            Tags.of(self.api_gateway).add(key, value)
        
        # Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            self.api_lambda,
            proxy=True
        )
        
        # API resources
        api_resource = self.api_gateway.root.add_resource('api')
        
        # Health check endpoint
        health_resource = api_resource.add_resource('health')
        health_resource.add_method('GET', lambda_integration)
        
        # Analysis endpoints
        analyze_resource = api_resource.add_resource('analyze')
        analyze_resource.add_method('POST', lambda_integration)
        
        analysis_resource = api_resource.add_resource('analysis')
        analysis_id_resource = analysis_resource.add_resource('{analysis_id}')
        analysis_id_resource.add_method('GET', lambda_integration)
        
        status_resource = analysis_id_resource.add_resource('status')
        status_resource.add_method('GET', lambda_integration)
        
        # Lambda permissions handled by IAM role above
