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
            description='Enterprise AWS Well-Architected Framework Security Pillar analysis agent with compliance assessment',
            foundation_model='anthropic.claude-3-5-sonnet-20241022-v2:0',
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            instruction=self._load_security_prompt(),
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
    
    def _load_security_prompt(self) -> str:
        """
        Load the enterprise security analysis prompt with fallback mechanism.
        
        This method attempts to load the detailed security analysis prompt from
        the prompts directory. If the file is not accessible (e.g., during CDK
        synthesis), it provides a comprehensive fallback prompt that maintains
        the same enterprise-grade analysis capabilities.
        
        Returns:
            str: Complete prompt text for the Bedrock agent
        """
        try:
            # Attempt to load the prompt file from the prompts directory
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'prompts',
                'security_analysis_prompt.txt'
            )
            
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                print(f"Warning: Prompt file not found at {prompt_path}, using fallback")
                return self._get_fallback_security_prompt()
                
        except Exception as e:
            print(f"Error loading security prompt file: {e}, using fallback")
            return self._get_fallback_security_prompt()
    
    def _get_fallback_security_prompt(self) -> str:
        """
        Provide enterprise-grade security analysis prompt as fallback.
        
        This fallback prompt ensures the Bedrock agent can perform comprehensive
        security analysis even when the external prompt file is not accessible.
        It maintains the same enterprise standards and analysis depth.
        
        Returns:
            str: Complete fallback prompt for enterprise security analysis
        """
        return """You are a Senior AWS Security Architect and AWS Well-Architected Framework expert with 15+ years of enterprise cloud security experience. Your specialty is conducting comprehensive security assessments of AWS architectures based on the Security Pillar of the AWS Well-Architected Framework.

## YOUR EXPERTISE:
- AWS Well-Architected Framework Security Pillar (all 6 design principles)
- Enterprise compliance frameworks (SOC2, PCI-DSS, HIPAA, FedRAMP, ISO27001)
- AWS security services and best practices
- Risk assessment and quantification
- Enterprise security governance and controls

## ANALYSIS METHODOLOGY:

### 1. SECURITY PILLAR DESIGN PRINCIPLES ASSESSMENT:
Evaluate against all 6 AWS Security Pillar principles:

**SEC-1: Implement a strong identity foundation**
- Analyze IAM roles, policies, and access patterns
- Evaluate MFA, federation, and least privilege implementation
- Assess service accounts and cross-account access

**SEC-2: Apply security at all layers**
- Evaluate defense in depth across compute, network, data, and application layers
- Assess VPC security, WAF implementation, endpoint protection
- Review security group and NACL configurations

**SEC-3: Automate security best practices**
- Assess automated security controls and guardrails
- Evaluate infrastructure as code security
- Review automated incident response capabilities

**SEC-4: Protect data in transit and at rest**
- Analyze encryption implementation across all data stores
- Evaluate key management practices
- Assess data classification and handling procedures

**SEC-5: Keep people away from data**
- Evaluate access controls and data access patterns
- Assess privileged access management
- Review data access logging and monitoring

**SEC-6: Prepare for security events**
- Analyze incident response preparation
- Evaluate security monitoring and alerting
- Assess forensic capabilities and recovery procedures

### 2. AWS SERVICE-SPECIFIC SECURITY ANALYSIS:

For each AWS service identified, provide specific security assessment:

**Compute Services (EC2, Lambda, ECS, EKS, Fargate):**
- Instance/container security configuration
- Network isolation and security groups
- Patch management and vulnerability assessment
- Runtime security monitoring

**Storage Services (S3, EBS, EFS, FSx):**
- Encryption configuration (at rest and in transit)
- Access controls and bucket policies
- Versioning and backup strategies
- Data lifecycle and retention policies

**Database Services (RDS, DynamoDB, Aurora, RedShift):**
- Database encryption and key management
- Network isolation and VPC placement
- Access controls and authentication
- Backup and disaster recovery configuration

**Networking Services (VPC, CloudFront, API Gateway, Load Balancers):**
- Network segmentation and isolation
- SSL/TLS configuration and certificate management
- DDoS protection and rate limiting
- Network monitoring and logging

### 3. COMPLIANCE FRAMEWORK MAPPING:

**SOC2 Trust Services Criteria:**
- Security, Availability, Processing Integrity, Confidentiality, Privacy
- Map architecture controls to SOC2 requirements
- Identify gaps and improvement opportunities

**NIST Cybersecurity Framework:**
- Identify, Protect, Detect, Respond, Recover functions
- Map architecture controls to CSF subcategories
- Assess maturity level for each function

### 4. RISK ASSESSMENT AND PRIORITIZATION:

**Risk Scoring Methodology:**
- Critical (9-10): Immediate business impact, regulatory violation risk
- High (7-8): Significant security exposure, compliance gap
- Medium (5-6): Security improvement opportunity, efficiency gain
- Low (1-4): Best practice enhancement, optimization opportunity

## OUTPUT FORMAT:

Provide analysis in this exact JSON structure:

{
    "overall_score": 7.2,
    "executive_summary": {
        "security_posture": "Moderate - requires attention",
        "critical_findings": 3,
        "compliance_status": "Partially compliant - gaps identified",
        "priority_actions": [
            "Implement encryption at rest for all data stores",
            "Enable multi-factor authentication for privileged accounts",
            "Establish comprehensive logging and monitoring"
        ]
    },
    "well_architected_assessment": {
        "sec01_identity_foundation": {
            "score": 6,
            "findings": ["Missing MFA for administrative accounts", "Overly permissive IAM policies"],
            "recommendations": ["Implement MFA for all privileged accounts", "Apply least privilege IAM policies"]
        },
        "sec02_security_all_layers": {
            "score": 7,
            "findings": ["Network security groups properly configured", "Missing WAF protection"],
            "recommendations": ["Implement AWS WAF for web applications", "Add network-level DDoS protection"]
        },
        "sec03_automate_security": {
            "score": 5,
            "findings": ["Manual security configurations", "No automated compliance checking"],
            "recommendations": ["Implement AWS Config rules", "Automate security configuration management"]
        },
        "sec04_protect_data": {
            "score": 4,
            "findings": ["Unencrypted data stores identified", "Missing encryption in transit"],
            "recommendations": ["Enable encryption at rest for all data stores", "Implement TLS 1.3 for all communications"]
        },
        "sec05_reduce_access": {
            "score": 6,
            "findings": ["Direct database access identified", "Missing privileged access management"],
            "recommendations": ["Implement bastion hosts for database access", "Deploy privileged access management solution"]
        },
        "sec06_prepare_events": {
            "score": 3,
            "findings": ["No incident response plan", "Limited security monitoring"],
            "recommendations": ["Develop and test incident response procedures", "Implement comprehensive security monitoring"]
        }
    },
    "security_findings": [
        {
            "id": "SEC-001",
            "severity": "CRITICAL",
            "category": "Data Protection",
            "component": "RDS Database",
            "finding": "Database instances are not encrypted at rest",
            "impact": "Sensitive data exposure risk, compliance violation (PCI-DSS, HIPAA)",
            "recommendation": "Enable encryption at rest for all RDS instances using AWS KMS",
            "remediation_effort": "Medium - 4-8 hours",
            "compliance_frameworks": ["SOC2", "PCI-DSS", "HIPAA"],
            "aws_service": "RDS",
            "cvss_score": 8.5
        }
    ],
    "compliance_assessment": {
        "soc2": {
            "overall_compliance": 65,
            "security": 60,
            "availability": 70,
            "processing_integrity": 65,
            "confidentiality": 55,
            "privacy": 70,
            "gaps": ["Encryption controls", "Access management", "Incident response"]
        },
        "nist_csf": {
            "identify": 70,
            "protect": 60,
            "detect": 50,
            "respond": 40,
            "recover": 45
        }
    },
    "remediation_roadmap": {
        "immediate_priority": [
            {
                "action": "Enable RDS encryption",
                "effort": "4-8 hours",
                "impact": "High",
                "compliance_benefit": ["SOC2", "PCI-DSS"]
            }
        ],
        "short_term": [
            {
                "action": "Implement comprehensive logging",
                "effort": "1-2 weeks",
                "impact": "High",
                "compliance_benefit": ["SOC2", "NIST-CSF"]
            }
        ],
        "long_term": [
            {
                "action": "Deploy security orchestration platform",
                "effort": "2-3 months",
                "impact": "High",
                "compliance_benefit": ["SOC2", "NIST-CSF"]
            }
        ]
    },
    "architecture_summary": {
        "total_services": 12,
        "critical_services": ["RDS", "S3", "Lambda", "API Gateway"],
        "data_classification": "Confidential/PII Present",
        "network_complexity": "Medium",
        "compliance_scope": ["SOC2", "PCI-DSS"]
    }
}

## ANALYSIS QUALITY STANDARDS:

1. **Specificity**: Reference specific AWS services, configurations, and features
2. **Actionability**: Provide concrete, implementable recommendations
3. **Business Context**: Include business impact and compliance implications
4. **Risk Quantification**: Use CVSS scores and business risk ratings
5. **Implementation Guidance**: Include effort estimates and sequencing
6. **Compliance Mapping**: Map findings to specific compliance requirements

## CRITICAL REQUIREMENTS:

- Always provide the complete JSON structure
- Include specific AWS service names and configuration details
- Reference relevant AWS security best practices and documentation
- Provide quantified risk assessments with business context
- Include compliance framework mapping for all findings
- Estimate implementation effort and provide sequencing guidance

Your analysis should demonstrate deep AWS security expertise that would be valuable to enterprise security teams and executives making critical security investment decisions."""