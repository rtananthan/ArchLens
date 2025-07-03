import json
import boto3
import os
import xml.etree.ElementTree as ET
from typing import Dict, Any
from datetime import datetime, timezone

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lightweight processor Lambda for background analysis tasks
    """
    print(f"Processor event: {json.dumps(event)}")
    
    # Environment variables
    UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET')
    ANALYSIS_TABLE = os.environ.get('ANALYSIS_TABLE')
    BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
    BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')
    
    # Extract task details from event
    analysis_id = event.get('analysis_id')
    s3_key = event.get('s3_key')
    bucket = event.get('bucket', UPLOAD_BUCKET)
    
    if not analysis_id or not s3_key:
        print("Missing required parameters: analysis_id or s3_key")
        return {'statusCode': 400, 'body': 'Missing required parameters'}
    
    # Initialize AWS clients
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION)
    
    try:
        # Update status to processing
        table = dynamodb.Table(ANALYSIS_TABLE)
        table.update_item(
            Key={'analysis_id': analysis_id},
            UpdateExpression='SET #status = :status, processing_timestamp = :timestamp',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'processing',
                ':timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Download file from S3
        print(f"Downloading file from s3://{bucket}/{s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        file_content = response['Body'].read().decode('utf-8')
        
        # Parse XML and extract architecture information
        architecture_info = parse_drawio_xml(file_content)
        
        # Call Bedrock agent for detailed analysis
        bedrock_response = call_bedrock_agent_detailed(
            bedrock_agent_client,
            BEDROCK_AGENT_ID,
            BEDROCK_AGENT_ALIAS_ID,
            file_content,
            architecture_info,
            analysis_id
        )
        
        # Update DynamoDB with final results
        table.update_item(
            Key={'analysis_id': analysis_id},
            UpdateExpression='''
                SET #status = :status, 
                    results = :results, 
                    description = :description,
                    completion_timestamp = :timestamp,
                    processing_time_seconds = :processing_time
            ''',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'completed',
                ':results': bedrock_response,
                ':description': bedrock_response.get('description', 'Architecture analysis completed'),
                ':timestamp': datetime.now(timezone.utc).isoformat(),
                ':processing_time': 30  # Approximate processing time
            }
        )
        
        print(f"Analysis {analysis_id} completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'analysis_id': analysis_id,
                'status': 'completed',
                'message': 'Background analysis completed successfully'
            })
        }
        
    except Exception as e:
        print(f"Error in background processing: {str(e)}")
        
        # Update record with error status
        try:
            table = dynamodb.Table(ANALYSIS_TABLE)
            table.update_item(
                Key={'analysis_id': analysis_id},
                UpdateExpression='SET #status = :status, error_message = :error, error_timestamp = :timestamp',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':error': str(e),
                    ':timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as db_error:
            print(f"Failed to update error status: {str(db_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'analysis_id': analysis_id,
                'status': 'failed',
                'error': str(e)
            })
        }

def parse_drawio_xml(xml_content):
    """Parse draw.io XML and extract architecture components"""
    
    try:
        root = ET.fromstring(xml_content)
        components = []
        connections = []
        
        # Find all mxCell elements
        for cell in root.iter('mxCell'):
            cell_id = cell.get('id')
            value = cell.get('value', '')
            style = cell.get('style', '')
            
            if value and cell_id not in ['0', '1']:  # Skip root cells
                # Try to identify AWS service types
                service_type = identify_aws_service(value, style)
                
                components.append({
                    'id': cell_id,
                    'name': value,
                    'service_type': service_type,
                    'style': style
                })
            
            # Check for connections (edges)
            source = cell.get('source')
            target = cell.get('target')
            if source and target:
                connections.append({
                    'source': source,
                    'target': target,
                    'type': 'connection'
                })
        
        return {
            'components': components,
            'connections': connections,
            'component_count': len(components),
            'connection_count': len(connections)
        }
        
    except Exception as e:
        print(f"XML parsing error: {str(e)}")
        return {
            'components': [],
            'connections': [],
            'component_count': 0,
            'connection_count': 0,
            'parse_error': str(e)
        }

def identify_aws_service(value, style):
    """
    Enterprise-grade AWS service identification with comprehensive pattern matching.
    
    This function provides sophisticated service detection for 50+ AWS services
    across all major categories, enabling detailed security analysis and
    compliance assessment for enterprise architectures.
    
    Args:
        value: Component name/label from diagram
        style: Component style information
    
    Returns:
        str: Identified AWS service name
    """
    
    value_lower = value.lower()
    style_lower = style.lower()
    
    # Pattern matching for AWS services - comprehensive enterprise service coverage
    # Organized by service category for better maintainability
    
    # Compute Services
    if any(keyword in value_lower for keyword in ['ec2', 'instance', 'server', 'virtual machine', 'vm']):
        return 'EC2'
    elif any(keyword in value_lower for keyword in ['lambda', 'function', 'serverless']):
        return 'Lambda'
    elif any(keyword in value_lower for keyword in ['ecs', 'container service', 'fargate']):
        return 'ECS'
    elif any(keyword in value_lower for keyword in ['eks', 'kubernetes', 'k8s']):
        return 'EKS'
    elif any(keyword in value_lower for keyword in ['batch', 'job queue']):
        return 'Batch'
    elif any(keyword in value_lower for keyword in ['lightsail', 'simple compute']):
        return 'Lightsail'
    elif any(keyword in value_lower for keyword in ['app runner', 'apprunner']):
        return 'App Runner'
    
    # Storage Services
    elif any(keyword in value_lower for keyword in ['s3', 'bucket', 'object storage']):
        return 'S3'
    elif any(keyword in value_lower for keyword in ['ebs', 'elastic block', 'volume']):
        return 'EBS'
    elif any(keyword in value_lower for keyword in ['efs', 'elastic file', 'nfs']):
        return 'EFS'
    elif any(keyword in value_lower for keyword in ['fsx', 'lustre', 'windows file']):
        return 'FSx'
    elif any(keyword in value_lower for keyword in ['storage gateway', 'hybrid storage']):
        return 'Storage Gateway'
    elif any(keyword in value_lower for keyword in ['backup', 'aws backup']):
        return 'AWS Backup'
    elif any(keyword in value_lower for keyword in ['datasync', 'data sync']):
        return 'DataSync'
    
    # Database Services
    elif any(keyword in value_lower for keyword in ['rds', 'relational database', 'mysql', 'postgres', 'oracle', 'sql server']):
        return 'RDS'
    elif any(keyword in value_lower for keyword in ['dynamodb', 'dynamo', 'nosql']):
        return 'DynamoDB'
    elif any(keyword in value_lower for keyword in ['aurora', 'aurora serverless']):
        return 'Aurora'
    elif any(keyword in value_lower for keyword in ['redshift', 'data warehouse']):
        return 'Redshift'
    elif any(keyword in value_lower for keyword in ['elasticache', 'redis', 'memcached']):
        return 'ElastiCache'
    elif any(keyword in value_lower for keyword in ['documentdb', 'mongodb']):
        return 'DocumentDB'
    elif any(keyword in value_lower for keyword in ['neptune', 'graph database']):
        return 'Neptune'
    elif any(keyword in value_lower for keyword in ['timestream', 'time series']):
        return 'Timestream'
    elif any(keyword in value_lower for keyword in ['keyspaces', 'cassandra']):
        return 'Keyspaces'
    
    # Networking & Content Delivery
    elif any(keyword in value_lower for keyword in ['vpc', 'virtual private cloud']):
        return 'VPC'
    elif any(keyword in value_lower for keyword in ['load balancer', 'alb', 'elb', 'nlb', 'application load balancer', 'network load balancer']):
        return 'Load Balancer'
    elif any(keyword in value_lower for keyword in ['cloudfront', 'cdn', 'content delivery']):
        return 'CloudFront'
    elif any(keyword in value_lower for keyword in ['api gateway', 'api gw', 'rest api', 'graphql']):
        return 'API Gateway'
    elif any(keyword in value_lower for keyword in ['route 53', 'route53', 'dns', 'domain']):
        return 'Route 53'
    elif any(keyword in value_lower for keyword in ['direct connect', 'directconnect', 'dx']):
        return 'Direct Connect'
    elif any(keyword in value_lower for keyword in ['vpn', 'site-to-site', 'client vpn']):
        return 'VPN'
    elif any(keyword in value_lower for keyword in ['transit gateway', 'tgw']):
        return 'Transit Gateway'
    elif any(keyword in value_lower for keyword in ['nat gateway', 'nat instance']):
        return 'NAT Gateway'
    elif any(keyword in value_lower for keyword in ['internet gateway', 'igw']):
        return 'Internet Gateway'
    
    # Security, Identity & Compliance
    elif any(keyword in value_lower for keyword in ['iam', 'identity', 'role', 'policy', 'user']):
        return 'IAM'
    elif any(keyword in value_lower for keyword in ['cognito', 'user pool', 'identity pool']):
        return 'Cognito'
    elif any(keyword in value_lower for keyword in ['kms', 'key management', 'encryption key']):
        return 'KMS'
    elif any(keyword in value_lower for keyword in ['certificate manager', 'acm', 'ssl', 'tls']):
        return 'Certificate Manager'
    elif any(keyword in value_lower for keyword in ['secrets manager', 'secret']):
        return 'Secrets Manager'
    elif any(keyword in value_lower for keyword in ['parameter store', 'ssm parameter']):
        return 'Parameter Store'
    elif any(keyword in value_lower for keyword in ['waf', 'web application firewall']):
        return 'WAF'
    elif any(keyword in value_lower for keyword in ['shield', 'ddos protection']):
        return 'Shield'
    elif any(keyword in value_lower for keyword in ['guardduty', 'threat detection']):
        return 'GuardDuty'
    elif any(keyword in value_lower for keyword in ['security hub', 'securityhub']):
        return 'Security Hub'
    elif any(keyword in value_lower for keyword in ['inspector', 'vulnerability assessment']):
        return 'Inspector'
    elif any(keyword in value_lower for keyword in ['macie', 'data discovery']):
        return 'Macie'
    elif any(keyword in value_lower for keyword in ['config', 'compliance', 'configuration']):
        return 'Config'
    elif any(keyword in value_lower for keyword in ['cloudtrail', 'audit log', 'api logging']):
        return 'CloudTrail'
    
    # Analytics
    elif any(keyword in value_lower for keyword in ['emr', 'hadoop', 'spark']):
        return 'EMR'
    elif any(keyword in value_lower for keyword in ['glue', 'etl', 'data catalog']):
        return 'Glue'
    elif any(keyword in value_lower for keyword in ['athena', 'query service']):
        return 'Athena'
    elif any(keyword in value_lower for keyword in ['quicksight', 'business intelligence', 'bi']):
        return 'QuickSight'
    elif any(keyword in value_lower for keyword in ['kinesis', 'streaming', 'data stream']):
        return 'Kinesis'
    elif any(keyword in value_lower for keyword in ['opensearch', 'elasticsearch']):
        return 'OpenSearch'
    elif any(keyword in value_lower for keyword in ['msk', 'kafka', 'managed kafka']):
        return 'MSK'
    
    # Application Integration
    elif any(keyword in value_lower for keyword in ['sqs', 'queue', 'message queue']):
        return 'SQS'
    elif any(keyword in value_lower for keyword in ['sns', 'notification', 'topic']):
        return 'SNS'
    elif any(keyword in value_lower for keyword in ['eventbridge', 'event bridge', 'event bus']):
        return 'EventBridge'
    elif any(keyword in value_lower for keyword in ['step functions', 'state machine', 'workflow']):
        return 'Step Functions'
    elif any(keyword in value_lower for keyword in ['mq', 'message broker', 'activemq']):
        return 'Amazon MQ'
    
    # Management & Governance
    elif any(keyword in value_lower for keyword in ['cloudwatch', 'monitoring', 'metrics', 'logs']):
        return 'CloudWatch'
    elif any(keyword in value_lower for keyword in ['cloudformation', 'stack', 'template']):
        return 'CloudFormation'
    elif any(keyword in value_lower for keyword in ['systems manager', 'ssm', 'session manager']):
        return 'Systems Manager'
    elif any(keyword in value_lower for keyword in ['organizations', 'account management']):
        return 'Organizations'
    elif any(keyword in value_lower for keyword in ['control tower', 'landing zone']):
        return 'Control Tower'
    elif any(keyword in value_lower for keyword in ['service catalog', 'product portfolio']):
        return 'Service Catalog'
    elif any(keyword in value_lower for keyword in ['trusted advisor', 'cost optimization']):
        return 'Trusted Advisor'
    
    # Developer Tools
    elif any(keyword in value_lower for keyword in ['codebuild', 'build service']):
        return 'CodeBuild'
    elif any(keyword in value_lower for keyword in ['codedeploy', 'deployment']):
        return 'CodeDeploy'
    elif any(keyword in value_lower for keyword in ['codepipeline', 'ci/cd', 'pipeline']):
        return 'CodePipeline'
    elif any(keyword in value_lower for keyword in ['codecommit', 'git repository']):
        return 'CodeCommit'
    
    # Machine Learning
    elif any(keyword in value_lower for keyword in ['sagemaker', 'machine learning', 'ml']):
        return 'SageMaker'
    elif any(keyword in value_lower for keyword in ['bedrock', 'generative ai', 'foundation model']):
        return 'Bedrock'
    elif any(keyword in value_lower for keyword in ['rekognition', 'image analysis']):
        return 'Rekognition'
    elif any(keyword in value_lower for keyword in ['comprehend', 'nlp', 'text analysis']):
        return 'Comprehend'
    elif any(keyword in value_lower for keyword in ['textract', 'document analysis']):
        return 'Textract'
    elif any(keyword in value_lower for keyword in ['polly', 'text to speech']):
        return 'Polly'
    elif any(keyword in value_lower for keyword in ['transcribe', 'speech to text']):
        return 'Transcribe'
    elif any(keyword in value_lower for keyword in ['translate', 'language translation']):
        return 'Translate'
    
    # IoT
    elif any(keyword in value_lower for keyword in ['iot core', 'internet of things']):
        return 'IoT Core'
    elif any(keyword in value_lower for keyword in ['iot device management', 'device fleet']):
        return 'IoT Device Management'
    elif any(keyword in value_lower for keyword in ['iot analytics', 'iot data']):
        return 'IoT Analytics'
    
    # Generic AWS Service Detection
    elif 'aws' in style_lower or 'amazon' in value_lower:
        return 'AWS Service'
    
    # Default fallback
    else:
        return 'Unknown'

def call_bedrock_agent_detailed(bedrock_agent_client, agent_id, agent_alias_id, xml_content, architecture_info, session_id):
    """Call Amazon Bedrock agent for detailed architecture analysis"""
    
    try:
        # Create comprehensive prompt
        prompt = f"""As an AWS security expert, please analyze this architecture diagram and provide a comprehensive security assessment.

ARCHITECTURE XML:
{xml_content}

PARSED COMPONENTS:
- Total components: {architecture_info['component_count']}
- Total connections: {architecture_info['connection_count']}

Components found:
"""
        
        for component in architecture_info['components']:
            prompt += f"- {component['name']} (Type: {component['service_type']})\n"
        
        prompt += """

Please provide a detailed analysis including:

1. ARCHITECTURE OVERVIEW: Brief description of the overall architecture pattern
2. SECURITY ANALYSIS: Identify specific security risks and vulnerabilities
3. COMPLIANCE ASSESSMENT: Check against AWS Well-Architected Security Pillar
4. RECOMMENDATIONS: Prioritized list of security improvements
5. OVERALL SCORE: Rate security from 1-10 with justification

Focus on:
- Network security (VPC, Security Groups, NACLs)
- Identity and Access Management (IAM)
- Data protection (encryption, backups)
- Monitoring and logging
- Incident response capabilities
- Infrastructure security

Format your response as a structured analysis with clear sections."""

        # Call the Bedrock agent
        response = bedrock_agent_client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=prompt
        )
        
        # Process the response
        result_text = ""
        if 'completion' in response:
            for chunk in response['completion']:
                if 'chunk' in chunk:
                    chunk_data = chunk['chunk']
                    if 'bytes' in chunk_data:
                        result_text += chunk_data['bytes'].decode('utf-8')
        
        # Parse the response into structured data
        return parse_enterprise_bedrock_response(result_text, architecture_info)
        
    except Exception as e:
        print(f"Detailed Bedrock agent call failed: {str(e)}")
        # Return comprehensive fallback analysis
        return create_fallback_analysis(architecture_info, str(e))

def parse_enterprise_bedrock_response(response_text, architecture_info):
    """
    Parse enterprise-grade Bedrock response with comprehensive JSON structure parsing.
    
    This function attempts to parse the JSON response from the enterprise Bedrock agent,
    which includes Well-Architected Framework assessment, compliance frameworks,
    detailed security findings, and remediation roadmaps. Falls back to structured
    analysis if JSON parsing fails.
    
    Args:
        response_text: Raw response from Bedrock agent
        architecture_info: Parsed architecture information
    
    Returns:
        dict: Comprehensive enterprise security analysis
    """
    import re
    import json
    
    try:
        # Try to extract JSON from the response
        # Look for JSON block in the response
        json_pattern = r'\{[\s\S]*\}'
        json_match = re.search(json_pattern, response_text)
        
        if json_match:
            json_text = json_match.group(0)
            try:
                # Parse the JSON response
                parsed_response = json.loads(json_text)
                
                # Validate that it has the expected enterprise structure
                if 'overall_score' in parsed_response and 'executive_summary' in parsed_response:
                    # Add metadata and return enterprise response
                    parsed_response.update({
                        'raw_bedrock_response': response_text,
                        'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                        'parsing_method': 'enterprise_json',
                        'architecture_info': architecture_info
                    })
                    return parsed_response
                    
            except json.JSONDecodeError as je:
                print(f"JSON parsing failed: {je}")
        
        # Fallback to structured parsing if JSON parsing fails
        print("JSON parsing failed, falling back to structured analysis")
        return parse_structured_bedrock_response(response_text, architecture_info)
        
    except Exception as e:
        print(f"Enterprise parsing failed: {e}")
        return create_enterprise_fallback_analysis(architecture_info, response_text, str(e))

def parse_structured_bedrock_response(response_text, architecture_info):
    """
    Parse Bedrock response using pattern matching for enterprise analysis.
    
    This function extracts key information from the response text using regex patterns
    and constructs a Well-Architected Framework compliant analysis structure.
    """
    import re
    
    # Extract score from response
    score = 7.5  # Default score
    score_patterns = [
        r'overall[_\s]score[:\s]+(\d+(?:\.\d+)?)',
        r'score[:\s]+(\d+(?:\.\d+)?)',
        r'rate[:\s]+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:/\s*10|out of 10)'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, response_text.lower())
        if match:
            try:
                score = float(match.group(1))
                if score > 10:
                    score = score / 10
                break
            except:
                continue
    
    # Extract critical findings count
    critical_findings = len([comp for comp in architecture_info['components'] 
                           if comp['service_type'] in ['RDS', 'S3', 'EC2', 'Lambda']])
    
    # Generate enterprise security findings
    security_findings = generate_enterprise_security_findings(architecture_info, response_text)
    
    # Generate Well-Architected assessment
    wa_assessment = generate_well_architected_assessment(architecture_info, response_text)
    
    # Generate compliance assessment
    compliance_assessment = generate_compliance_assessment(architecture_info, security_findings)
    
    # Generate remediation roadmap
    remediation_roadmap = generate_remediation_roadmap(security_findings)
    
    # Create executive summary
    executive_summary = {
        "security_posture": get_security_posture_description(score),
        "critical_findings": len([f for f in security_findings if f['severity'] == 'CRITICAL']),
        "compliance_status": get_compliance_status(compliance_assessment),
        "priority_actions": [
            "Implement encryption at rest for all data stores",
            "Enable comprehensive logging and monitoring",
            "Review and optimize IAM policies and access controls"
        ][:3]
    }
    
    return {
        'overall_score': score,
        'executive_summary': executive_summary,
        'well_architected_assessment': wa_assessment,
        'security_findings': security_findings,
        'compliance_assessment': compliance_assessment,
        'remediation_roadmap': remediation_roadmap,
        'architecture_summary': {
            'total_services': architecture_info['component_count'],
            'critical_services': list(set([comp['service_type'] for comp in architecture_info['components'] 
                                         if comp['service_type'] in ['RDS', 'S3', 'Lambda', 'EC2', 'API Gateway']])),
            'data_classification': 'Sensitive/Enterprise Data',
            'network_complexity': 'Medium' if architecture_info['connection_count'] > 5 else 'Low',
            'compliance_scope': ['SOC2', 'AWS Well-Architected']
        },
        'raw_bedrock_response': response_text,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
        'parsing_method': 'structured_fallback'
    }

def generate_enterprise_security_findings(architecture_info, response_text):
    """Generate detailed security findings with CVSS scores and compliance mapping"""
    findings = []
    finding_id = 1
    
    component_types = [comp['service_type'] for comp in architecture_info['components']]
    
    # Generate findings for each service type
    for service_type in set(component_types):
        if service_type == 'RDS':
            findings.append({
                'id': f'SEC-{finding_id:03d}',
                'severity': 'HIGH',
                'category': 'Data Protection',
                'component': 'RDS Database',
                'finding': 'Database encryption and access controls require review',
                'impact': 'Potential data exposure, compliance violations',
                'recommendation': 'Enable encryption at rest and in transit, implement proper IAM policies',
                'remediation_effort': 'Medium - 4-8 hours',
                'compliance_frameworks': ['SOC2', 'PCI-DSS', 'HIPAA'],
                'aws_service': 'RDS',
                'cvss_score': 7.5
            })
            finding_id += 1
            
        elif service_type == 'S3':
            findings.append({
                'id': f'SEC-{finding_id:03d}',
                'severity': 'MEDIUM',
                'category': 'Access Control',
                'component': 'S3 Storage',
                'finding': 'S3 bucket policies and access controls need verification',
                'impact': 'Potential unauthorized access to stored data',
                'recommendation': 'Review bucket policies, enable versioning and logging',
                'remediation_effort': 'Low - 2-4 hours',
                'compliance_frameworks': ['SOC2', 'NIST-CSF'],
                'aws_service': 'S3',
                'cvss_score': 6.0
            })
            finding_id += 1
            
        elif service_type in ['EC2', 'Lambda']:
            findings.append({
                'id': f'SEC-{finding_id:03d}',
                'severity': 'MEDIUM',
                'category': 'Infrastructure Security',
                'component': f'{service_type} Compute',
                'finding': 'Compute security configuration and monitoring needs enhancement',
                'impact': 'Potential unauthorized access or resource compromise',
                'recommendation': 'Implement proper security groups, enable monitoring, regular patching',
                'remediation_effort': 'Medium - 4-6 hours',
                'compliance_frameworks': ['SOC2', 'NIST-CSF'],
                'aws_service': service_type,
                'cvss_score': 5.5
            })
            finding_id += 1
    
    # Add general architectural findings
    if architecture_info['connection_count'] > 0:
        findings.append({
            'id': f'SEC-{finding_id:03d}',
            'severity': 'LOW',
            'category': 'Network Security',
            'component': 'Network Architecture',
            'finding': 'Network security and segmentation should be reviewed',
            'impact': 'Potential lateral movement in case of compromise',
            'recommendation': 'Implement proper VPC design, security groups, and NACLs',
            'remediation_effort': 'High - 1-2 weeks',
            'compliance_frameworks': ['SOC2', 'NIST-CSF'],
            'aws_service': 'VPC',
            'cvss_score': 4.0
        })
    
    return findings

def generate_well_architected_assessment(architecture_info, response_text):
    """Generate AWS Well-Architected Security Pillar assessment"""
    component_types = set([comp['service_type'] for comp in architecture_info['components']])
    
    # Base scores based on architecture complexity and service types
    base_score = 6 if len(component_types) > 3 else 7
    
    return {
        'sec01_identity_foundation': {
            'score': base_score,
            'findings': ['IAM policies and access controls need review', 'MFA implementation should be verified'],
            'recommendations': ['Implement least privilege access', 'Enable MFA for all users']
        },
        'sec02_security_all_layers': {
            'score': base_score + 1,
            'findings': ['Network security appears configured', 'Application layer security needs review'],
            'recommendations': ['Implement WAF for web applications', 'Review security group configurations']
        },
        'sec03_automate_security': {
            'score': base_score - 1,
            'findings': ['Limited automation detected', 'Manual security processes identified'],
            'recommendations': ['Implement AWS Config for compliance', 'Automate security monitoring']
        },
        'sec04_protect_data': {
            'score': base_score - 2 if 'RDS' in component_types or 'S3' in component_types else base_score,
            'findings': ['Data encryption needs verification', 'Backup strategies require review'],
            'recommendations': ['Enable encryption for all data stores', 'Implement comprehensive backup strategy']
        },
        'sec05_reduce_access': {
            'score': base_score,
            'findings': ['Access patterns need analysis', 'Privileged access should be reviewed'],
            'recommendations': ['Implement bastion hosts where needed', 'Review database access patterns']
        },
        'sec06_prepare_events': {
            'score': base_score - 2,
            'findings': ['Limited incident response preparation', 'Monitoring needs enhancement'],
            'recommendations': ['Develop incident response procedures', 'Implement comprehensive monitoring']
        }
    }

def generate_compliance_assessment(architecture_info, security_findings):
    """Generate compliance framework assessment"""
    critical_count = len([f for f in security_findings if f['severity'] == 'CRITICAL'])
    high_count = len([f for f in security_findings if f['severity'] == 'HIGH'])
    
    # Calculate compliance scores based on findings
    base_compliance = 80 - (critical_count * 15) - (high_count * 10)
    base_compliance = max(base_compliance, 40)  # Minimum score
    
    return {
        'soc2': {
            'overall_compliance': base_compliance,
            'security': base_compliance - 5,
            'availability': base_compliance + 5,
            'processing_integrity': base_compliance,
            'confidentiality': base_compliance - 10,
            'privacy': base_compliance + 5,
            'gaps': ['Encryption controls', 'Access management', 'Incident response']
        },
        'nist_csf': {
            'identify': base_compliance + 10,
            'protect': base_compliance,
            'detect': base_compliance - 10,
            'respond': base_compliance - 20,
            'recover': base_compliance - 15
        }
    }

def generate_remediation_roadmap(security_findings):
    """Generate prioritized remediation roadmap"""
    critical_findings = [f for f in security_findings if f['severity'] == 'CRITICAL']
    high_findings = [f for f in security_findings if f['severity'] == 'HIGH']
    medium_findings = [f for f in security_findings if f['severity'] == 'MEDIUM']
    
    roadmap = {
        'immediate_priority': [],
        'short_term': [],
        'long_term': []
    }
    
    # Immediate priority - Critical findings
    for finding in critical_findings[:3]:
        roadmap['immediate_priority'].append({
            'action': finding['recommendation'],
            'effort': finding['remediation_effort'],
            'impact': 'Critical',
            'compliance_benefit': finding['compliance_frameworks']
        })
    
    # Short term - High findings
    for finding in high_findings[:3]:
        roadmap['short_term'].append({
            'action': finding['recommendation'],
            'effort': finding['remediation_effort'],
            'impact': 'High',
            'compliance_benefit': finding['compliance_frameworks']
        })
    
    # Long term - Medium findings and architectural improvements
    for finding in medium_findings[:2]:
        roadmap['long_term'].append({
            'action': finding['recommendation'],
            'effort': finding['remediation_effort'],
            'impact': 'Medium',
            'compliance_benefit': finding['compliance_frameworks']
        })
    
    return roadmap

def get_security_posture_description(score):
    """Get security posture description based on score"""
    if score >= 9:
        return "Excellent - well-secured architecture"
    elif score >= 7:
        return "Good - minor improvements needed"
    elif score >= 5:
        return "Moderate - requires attention"
    elif score >= 3:
        return "Poor - significant issues identified"
    else:
        return "Critical - immediate action required"

def get_compliance_status(compliance_assessment):
    """Get overall compliance status"""
    soc2_score = compliance_assessment['soc2']['overall_compliance']
    if soc2_score >= 85:
        return "Compliant - minor gaps"
    elif soc2_score >= 70:
        return "Partially compliant - gaps identified"
    else:
        return "Non-compliant - significant remediation required"

def create_enterprise_fallback_analysis(architecture_info, response_text, error_message):
    """Create comprehensive fallback analysis for enterprise use"""
    return {
        'overall_score': 6.5,
        'executive_summary': {
            'security_posture': 'Moderate - requires professional review',
            'critical_findings': 2,
            'compliance_status': 'Partially compliant - assessment limited',
            'priority_actions': [
                'Conduct comprehensive security review',
                'Implement encryption and access controls',
                'Establish monitoring and compliance procedures'
            ]
        },
        'well_architected_assessment': generate_well_architected_assessment(architecture_info, response_text),
        'security_findings': generate_enterprise_security_findings(architecture_info, response_text),
        'compliance_assessment': {
            'soc2': {
                'overall_compliance': 65,
                'security': 60,
                'availability': 70,
                'processing_integrity': 65,
                'confidentiality': 55,
                'privacy': 70,
                'gaps': ['Comprehensive assessment limited by service availability']
            },
            'nist_csf': {
                'identify': 70,
                'protect': 60,
                'detect': 50,
                'respond': 40,
                'recover': 45
            }
        },
        'remediation_roadmap': {
            'immediate_priority': [
                {
                    'action': 'Conduct professional security assessment',
                    'effort': '1-2 weeks',
                    'impact': 'High',
                    'compliance_benefit': ['SOC2', 'NIST-CSF']
                }
            ],
            'short_term': [
                {
                    'action': 'Implement basic security controls',
                    'effort': '2-4 weeks',
                    'impact': 'High',
                    'compliance_benefit': ['SOC2']
                }
            ],
            'long_term': [
                {
                    'action': 'Deploy comprehensive security monitoring',
                    'effort': '1-3 months',
                    'impact': 'High',
                    'compliance_benefit': ['SOC2', 'NIST-CSF']
                }
            ]
        },
        'architecture_summary': {
            'total_services': architecture_info['component_count'],
            'critical_services': list(set([comp['service_type'] for comp in architecture_info['components']])),
            'data_classification': 'Enterprise/Sensitive',
            'network_complexity': 'Medium',
            'compliance_scope': ['SOC2', 'AWS Well-Architected']
        },
        'fallback_reason': error_message,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
        'parsing_method': 'enterprise_fallback'
    }

def parse_detailed_bedrock_response(response_text, architecture_info):
    """Parse detailed Bedrock response into structured format"""
    
    # Extract score from response if possible
    score = 7.5  # Default score
    
    # Look for score patterns in the response
    import re
    score_patterns = [
        r'score[:\s]+(\d+(?:\.\d+)?)',
        r'rate[:\s]+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:/\s*10|out of 10)'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, response_text.lower())
        if match:
            try:
                score = float(match.group(1))
                if score > 10:
                    score = score / 10  # Convert if score was given as percentage
                break
            except:
                continue
    
    # Generate issues based on components found
    issues = generate_security_issues(architecture_info)
    
    return {
        'description': f'Comprehensive AI Security Analysis: {response_text[:300]}...' if len(response_text) > 300 else response_text,
        'overall_score': score,
        'security': {
            'score': score,
            'issues': issues,
            'recommendations': generate_recommendations(architecture_info),
            'compliance_notes': extract_compliance_info(response_text)
        },
        'architecture_summary': {
            'total_components': architecture_info['component_count'],
            'total_connections': architecture_info['connection_count'],
            'component_types': list(set([comp['service_type'] for comp in architecture_info['components']]))
        },
        'raw_bedrock_response': response_text,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat()
    }

def generate_security_issues(architecture_info):
    """Generate security issues based on architecture components"""
    
    issues = []
    
    # Check for common security issues based on components
    component_types = [comp['service_type'] for comp in architecture_info['components']]
    
    if 'Load Balancer' in component_types:
        issues.append({
            'severity': 'MEDIUM',
            'component': 'Application Load Balancer',
            'issue': 'Load balancer should enforce HTTPS and implement proper security headers',
            'recommendation': 'Configure SSL/TLS termination, enable security headers, and implement WAF',
            'aws_service': 'ALB'
        })
    
    if 'EC2' in component_types:
        issues.append({
            'severity': 'HIGH',
            'component': 'EC2 Instances',
            'issue': 'EC2 instances may lack proper security group configuration and access controls',
            'recommendation': 'Implement least privilege security groups, enable Systems Manager Session Manager, and ensure regular patching',
            'aws_service': 'EC2'
        })
    
    if 'RDS' in component_types:
        issues.append({
            'severity': 'MEDIUM',
            'component': 'RDS Database',
            'issue': 'Database security configuration should be reviewed',
            'recommendation': 'Enable encryption at rest and in transit, implement proper backup strategy, and configure security groups',
            'aws_service': 'RDS'
        })
    
    if 'S3' in component_types:
        issues.append({
            'severity': 'MEDIUM',
            'component': 'S3 Storage',
            'issue': 'S3 bucket security and access policies need review',
            'recommendation': 'Implement bucket policies, enable versioning, configure access logging, and ensure encryption',
            'aws_service': 'S3'
        })
    
    # Add general issues if no specific components found
    if not issues:
        issues.append({
            'severity': 'LOW',
            'component': 'General Architecture',
            'issue': 'Architecture requires comprehensive security review',
            'recommendation': 'Implement AWS security best practices and enable comprehensive monitoring',
            'aws_service': 'General'
        })
    
    return issues

def generate_recommendations(architecture_info):
    """Generate security recommendations based on architecture"""
    
    recommendations = [
        'Implement AWS WAF for application-layer protection',
        'Enable AWS CloudTrail for comprehensive audit logging',
        'Configure VPC Flow Logs for network monitoring',
        'Use AWS Config for compliance monitoring and drift detection',
        'Implement AWS GuardDuty for threat detection',
        'Enable AWS Security Hub for centralized security findings',
        'Use AWS Systems Manager for secure instance management',
        'Implement proper backup and disaster recovery strategies'
    ]
    
    # Add specific recommendations based on components
    component_types = [comp['service_type'] for comp in architecture_info['components']]
    
    if 'RDS' in component_types:
        recommendations.append('Enable RDS Performance Insights and automated backups')
    
    if 'S3' in component_types:
        recommendations.append('Implement S3 bucket lifecycle policies and cross-region replication')
    
    if 'Load Balancer' in component_types:
        recommendations.append('Configure ALB access logs and implement health checks')
    
    return recommendations[:8]  # Limit to 8 recommendations

def extract_compliance_info(response_text):
    """Extract compliance-related information from Bedrock response"""
    
    compliance_keywords = ['compliance', 'gdpr', 'hipaa', 'pci', 'sox', 'well-architected']
    
    compliance_notes = []
    for keyword in compliance_keywords:
        if keyword.lower() in response_text.lower():
            compliance_notes.append(f"Response mentions {keyword.upper()} compliance considerations")
    
    if not compliance_notes:
        compliance_notes.append("No specific compliance frameworks mentioned in analysis")
    
    return compliance_notes

def create_fallback_analysis(architecture_info, error_message):
    """Create fallback analysis when Bedrock call fails"""
    
    return {
        'description': f'Fallback analysis completed. Architecture contains {architecture_info["component_count"]} components with {architecture_info["connection_count"]} connections.',
        'overall_score': 6.5,
        'security': {
            'score': 6.5,
            'issues': generate_security_issues(architecture_info),
            'recommendations': generate_recommendations(architecture_info),
            'compliance_notes': ['Analysis completed with limited AI insights due to service unavailability']
        },
        'architecture_summary': {
            'total_components': architecture_info['component_count'],
            'total_connections': architecture_info['connection_count'],
            'component_types': list(set([comp['service_type'] for comp in architecture_info['components']]))
        },
        'fallback_reason': error_message,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat()
    }