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
    """Identify AWS service type based on component name and style"""
    
    value_lower = value.lower()
    style_lower = style.lower()
    
    # Common AWS service patterns
    if any(keyword in value_lower for keyword in ['load balancer', 'alb', 'elb', 'nlb']):
        return 'Load Balancer'
    elif any(keyword in value_lower for keyword in ['ec2', 'instance', 'server']):
        return 'EC2'
    elif any(keyword in value_lower for keyword in ['rds', 'database', 'db']):
        return 'RDS'
    elif any(keyword in value_lower for keyword in ['s3', 'bucket', 'storage']):
        return 'S3'
    elif any(keyword in value_lower for keyword in ['vpc', 'subnet']):
        return 'VPC'
    elif any(keyword in value_lower for keyword in ['cloudfront', 'cdn']):
        return 'CloudFront'
    elif any(keyword in value_lower for keyword in ['lambda', 'function']):
        return 'Lambda'
    elif any(keyword in value_lower for keyword in ['api gateway', 'api']):
        return 'API Gateway'
    elif any(keyword in value_lower for keyword in ['route 53', 'dns']):
        return 'Route 53'
    elif any(keyword in value_lower for keyword in ['iam', 'role', 'policy']):
        return 'IAM'
    elif any(keyword in value_lower for keyword in ['cloudwatch', 'monitoring']):
        return 'CloudWatch'
    elif 'aws' in style_lower:
        return 'AWS Service'
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
        return parse_detailed_bedrock_response(result_text, architecture_info)
        
    except Exception as e:
        print(f"Detailed Bedrock agent call failed: {str(e)}")
        # Return comprehensive fallback analysis
        return create_fallback_analysis(architecture_info, str(e))

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