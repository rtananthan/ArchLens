from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_bedrock as bedrock,
    Tags
)
from constructs import Construct
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tags import get_service_specific_tags, validate_tags

class AIStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, environment: str = 'dev', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.deployment_env = environment
        
        # IAM role for Bedrock agent
        self.bedrock_agent_role = iam.Role(
            self, 'BedrockAgentRole',
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'),
            inline_policies={
                'BedrockAgentPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'bedrock:InvokeModel',
                                'bedrock:InvokeModelWithResponseStream'
                            ],
                            resources=[
                                f'arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                                f'arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0'
                            ]
                        )
                    ]
                )
            }
        )
        
        # Add tags for Bedrock agent role
        bedrock_role_tags = get_service_specific_tags(
            'Bedrock-Agent-Execution-Role',
            'ai',
            {
                'IAMResourceType': 'Service-Role',
                'PermissionScope': 'Bedrock-Models'
            }
        )
        
        for key, value in validate_tags(bedrock_role_tags).items():
            Tags.of(self.bedrock_agent_role).add(key, value)
        
        # Bedrock agent for AWS security analysis
        self.security_analysis_agent = bedrock.CfnAgent(
            self, 'SecurityAnalysisAgent',
            agent_name='ArchLens-Security-Analyzer',
            description='AWS Well-Architected Framework security analysis agent for draw.io diagrams',
            foundation_model='anthropic.claude-3-sonnet-20240229-v1:0',
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            instruction='''You are an AWS security architecture expert specializing in the AWS Well-Architected Framework Security Pillar.

Your task is to analyze AWS architecture diagrams (provided as draw.io XML) and provide security assessments based on AWS best practices.

ANALYSIS PROCESS:
1. Parse the draw.io XML to identify AWS services and their configurations
2. Analyze security aspects including:
   - Data protection in transit and at rest
   - Identity and access management
   - Infrastructure protection
   - Detective controls
   - Incident response preparation

RESPONSE FORMAT:
Provide your analysis as a structured JSON response with:
- overall_score: Number (0-10) representing overall security posture
- security: Object containing:
  - score: Number (0-10) for security pillar score
  - issues: Array of security issues found
  - recommendations: Array of improvement recommendations

ISSUE FORMAT:
Each issue should include:
- severity: "HIGH", "MEDIUM", or "LOW"
- component: AWS service or component name
- issue: Description of the security concern
- recommendation: Specific remediation advice
- aws_service: The specific AWS service involved

Focus on actionable, specific recommendations that follow AWS security best practices and the Well-Architected Framework principles.''',
            idle_session_ttl_in_seconds=900,  # 15 minutes
            auto_prepare=True
        )
        
        # IAM role for Lambda functions to invoke Bedrock
        self.bedrock_invoke_role = iam.Role(
            self, 'BedrockInvokeRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ],
            inline_policies={
                'BedrockInvokePolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'bedrock-agent-runtime:InvokeAgent',
                                'bedrock-runtime:InvokeModel',
                                'bedrock-runtime:InvokeModelWithResponseStream'
                            ],
                            resources=[
                                self.security_analysis_agent.attr_agent_arn,
                                f'arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                                f'arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0'
                            ]
                        )
                    ]
                )
            }
        )