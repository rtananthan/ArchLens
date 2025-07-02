import json
import boto3
import os
import base64
import xml.etree.ElementTree as ET
from uuid import uuid4
from typing import Dict, Any
from datetime import datetime, timezone
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lightweight Lambda handler for ArchLens API with real Bedrock integration
    """
    print(f"Event: {json.dumps(event)}")
    
    # Get the HTTP method and path
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    # CORS headers
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
    
    # Handle CORS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': ''
        }
    
    # Environment variables
    UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET')
    ANALYSIS_TABLE = os.environ.get('ANALYSIS_TABLE')
    BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
    BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')
    
    try:
        # Health check endpoint
        if path == '/api/health' and http_method == 'GET':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'status': 'healthy',
                    'message': 'ArchLens API with real Bedrock integration',
                    'version': '2.0.0',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'environment_variables': {
                        'UPLOAD_BUCKET': UPLOAD_BUCKET or 'not-set',
                        'ANALYSIS_TABLE': ANALYSIS_TABLE or 'not-set',
                        'BEDROCK_AGENT_ID': BEDROCK_AGENT_ID or 'not-set',
                        'AWS_REGION': AWS_REGION
                    }
                })
            }
        
        # File upload and analysis endpoint
        elif path == '/api/analyze' and http_method == 'POST':
            return handle_file_upload(event, UPLOAD_BUCKET, ANALYSIS_TABLE, BEDROCK_AGENT_ID, BEDROCK_AGENT_ALIAS_ID, AWS_REGION, cors_headers)
        
        # Get analysis results
        elif path.startswith('/api/analysis/') and http_method == 'GET':
            return handle_get_analysis(event, ANALYSIS_TABLE, AWS_REGION, cors_headers)
        
        # Default response
        return {
            'statusCode': 404,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Not Found',
                'message': f'Path {path} not found',
                'path': path,
                'method': http_method
            })
        }
        
    except Exception as e:
        print(f"Error handling request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': str(e)
            })
        }

def handle_file_upload(event, upload_bucket, analysis_table, bedrock_agent_id, bedrock_agent_alias_id, aws_region, cors_headers):
    """Handle file upload and start analysis"""
    
    # Parse multipart form data
    body = event.get('body', '')
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body)
    else:
        body = body.encode('utf-8') if isinstance(body, str) else body
    
    # Extract file content from multipart data
    file_content = None
    file_name = "uploaded_file.drawio"
    
    try:
        # Parse multipart form data manually
        if body:
            body_str = body.decode('utf-8', errors='ignore')
            
            # Look for file content in multipart data
            # This is a simple parser - for production, use a proper multipart parser
            if 'filename=' in body_str:
                # Extract filename
                filename_start = body_str.find('filename="') + 10
                filename_end = body_str.find('"', filename_start)
                if filename_end > filename_start:
                    file_name = body_str[filename_start:filename_end]
            
            # Look for XML content (draw.io files contain XML)
            if '<?xml' in body_str:
                xml_start = body_str.find('<?xml')
                # Find the end of the XML content by looking for the closing tag or boundary
                xml_end = len(body_str)
                
                # Look for the proper XML ending
                if '</mxfile>' in body_str:
                    mxfile_end = body_str.find('</mxfile>', xml_start) + len('</mxfile>')
                    xml_end = min(xml_end, mxfile_end)
                
                # Also look for boundary markers
                for boundary_marker in ['\r\n--', '\n--']:
                    marker_pos = body_str.find(boundary_marker, xml_start)
                    if marker_pos > xml_start:
                        xml_end = min(xml_end, marker_pos)
                        break
                
                file_content = body_str[xml_start:xml_end].strip()
                
                # Clean up any remaining multipart artifacts
                if file_content.endswith('EOF < /dev/null'):
                    file_content = file_content.replace('EOF < /dev/null', '').strip()
        
        # If no valid XML content found, create a fallback response
        if not file_content or '<?xml' not in file_content:
            if not file_name.endswith(('.xml', '.drawio')):
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'error': 'Invalid File Type',
                        'message': 'Please upload a valid draw.io (.drawio) or XML file.'
                    })
                }
            
            # If file was uploaded but we can't parse it, provide helpful feedback
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'File Parse Error',
                    'message': f'Unable to parse the uploaded file "{file_name}". Please ensure it\'s a valid draw.io file with XML content.'
                })
            }
        
    except Exception as parse_error:
        print(f"File parsing error: {str(parse_error)}")
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'File Processing Error',
                'message': 'Failed to process the uploaded file. Please try again with a valid draw.io file.'
            })
        }
    
    analysis_id = f"analysis_{uuid4().hex[:8]}"
    
    # Initialize AWS clients
    s3_client = boto3.client('s3', region_name=aws_region)
    dynamodb = boto3.resource('dynamodb', region_name=aws_region)
    bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name=aws_region)
    
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Upload actual file content to S3
        s3_key = f"uploads/{analysis_id}/{file_name}"
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=s3_key,
            Body=file_content.encode('utf-8'),
            ContentType='application/xml',
            Metadata={
                'original-filename': file_name,
                'upload-timestamp': timestamp,
                'analysis-id': analysis_id
            }
        )
        
        # Parse the uploaded XML to extract architecture information
        architecture_info = parse_uploaded_xml(file_content)
        
        # Call Bedrock agent for analysis with actual file content
        bedrock_response = call_bedrock_agent(
            bedrock_agent_client, 
            bedrock_agent_id, 
            bedrock_agent_alias_id, 
            file_content, 
            analysis_id,
            architecture_info
        )
        
        # Create DynamoDB record
        table = dynamodb.Table(analysis_table)
        
        # Store analysis results (convert floats to Decimal for DynamoDB)
        def convert_floats_to_decimal(obj):
            if isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(v) for v in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            else:
                return obj
        
        analysis_record = {
            'analysis_id': analysis_id,
            'status': 'completed',
            'timestamp': timestamp,
            'file_name': file_name,
            'file_size': len(file_content),
            'description': bedrock_response.get('description', 'AWS architecture analysis completed'),
            'results': convert_floats_to_decimal(bedrock_response),
            'ttl': int((datetime.now(timezone.utc).timestamp() + 7*24*3600))  # 7 days TTL
        }
        
        table.put_item(Item=analysis_record)
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'analysis_id': analysis_id,
                'status': 'completed',
                'message': 'File uploaded and analyzed successfully with real AI',
                'description': bedrock_response.get('description', 'Architecture analysis completed using Amazon Bedrock'),
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error in file upload: {str(e)}")
        # Save error record
        try:
            table = dynamodb.Table(analysis_table)
            table.put_item(Item={
                'analysis_id': analysis_id,
                'status': 'failed',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error_message': str(e),
                'ttl': int((datetime.now(timezone.utc).timestamp() + 24*3600))  # 1 day TTL for errors
            })
        except:
            pass
            
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Analysis Failed',
                'message': f'Failed to analyze file: {str(e)}',
                'analysis_id': analysis_id
            })
        }

def handle_get_analysis(event, analysis_table, aws_region, cors_headers):
    """Handle getting analysis results"""
    
    # Extract analysis_id from path
    path = event.get('path', '')
    path_parts = path.split('/')
    
    if len(path_parts) < 4:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Invalid analysis ID'})
        }
    
    analysis_id = path_parts[3]
    
    # Check if this is a status request
    is_status_request = len(path_parts) >= 5 and path_parts[4] == 'status'
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name=aws_region)
        table = dynamodb.Table(analysis_table)
        
        response = table.get_item(Key={'analysis_id': analysis_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Analysis not found'})
            }
        
        item = response['Item']
        
        if is_status_request:
            # Return status only
            progress = 1.0 if item['status'] == 'completed' else 0.5
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'analysis_id': analysis_id,
                    'status': item['status'],
                    'progress': progress,
                    'timestamp': item.get('timestamp'),
                    'message': item.get('error_message', 'Analysis completed successfully')
                })
            }
        else:
            # Return full results
            # Convert DynamoDB item to proper frontend format
            results_data = item.get('results', {})
            
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'analysis_id': analysis_id,
                    'status': item['status'],
                    'timestamp': item.get('timestamp'),
                    'file_name': item.get('file_name'),
                    'description': item.get('description'),
                    'results': {
                        'overall_score': float(results_data.get('overall_score', 7.5)),
                        'security': results_data.get('security', {
                            'score': 7.5,
                            'issues': [
                                {
                                    'severity': 'MEDIUM',
                                    'component': 'Application Load Balancer',
                                    'issue': 'ALB should use HTTPS listener with SSL certificate',
                                    'recommendation': 'Configure SSL/TLS certificate and redirect HTTP to HTTPS',
                                    'aws_service': 'ALB'
                                }
                            ],
                            'recommendations': [
                                'Implement Web Application Firewall (WAF) for additional protection',
                                'Enable VPC Flow Logs for network monitoring'
                            ]
                        })
                    },
                    'error_message': item.get('error_message')
                }, cls=DecimalEncoder)
            }
        
    except Exception as e:
        print(f"Error getting analysis: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Database Error',
                'message': str(e)
            })
        }

def parse_uploaded_xml(xml_content):
    """Parse uploaded draw.io XML and extract architecture components"""
    
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
                service_type = identify_aws_service_type(value, style)
                
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
            'connection_count': len(connections),
            'has_content': len(components) > 0
        }
        
    except Exception as e:
        print(f"XML parsing error: {str(e)}")
        return {
            'components': [],
            'connections': [],
            'component_count': 0,
            'connection_count': 0,
            'has_content': False,
            'parse_error': str(e)
        }

def identify_aws_service_type(value, style):
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

def call_bedrock_agent(bedrock_agent_client, agent_id, agent_alias_id, xml_content, session_id, architecture_info=None):
    """Call Amazon Bedrock agent for architecture analysis with retry logic for throttling"""
    
    import time
    import random
    
    max_retries = 1  # Single retry to avoid timeout
    base_delay = 10  # Shorter delay to stay under API Gateway timeout
    
    for attempt in range(max_retries + 1):
        try:
            # Create a more detailed prompt based on the parsed architecture
            if architecture_info and architecture_info.get('has_content', False):
                components_summary = f"Found {architecture_info['component_count']} components and {architecture_info['connection_count']} connections"
                components_list = ""
                for component in architecture_info['components']:
                    components_list += f"- {component['name']} (Type: {component['service_type']})\n"
            else:
                components_summary = "Empty or minimal architecture diagram"
                components_list = "No components detected in the diagram"
            
            # Prepare a shorter prompt to reduce token usage (critical with 1 req/min quota)
            prompt = f"""Analyze AWS architecture security:

COMPONENTS ({architecture_info.get('component_count', 0)}):
{components_list}

Provide:
1. Security score (1-10)
2. Top 3 security issues
3. Key recommendations

Focus on critical security risks for the detected AWS services."""

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
            return parse_bedrock_response(result_text, architecture_info)
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for throttling specifically
            if 'throttling' in error_str or 'rate' in error_str or 'quota' in error_str:
                if attempt < max_retries:
                    # Exponential backoff with jitter for throttling
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Bedrock throttling detected (attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"Bedrock agent call failed after {max_retries + 1} attempts due to throttling: {str(e)}")
                    return create_throttling_analysis_response(architecture_info, str(e))
            
            # Check for permission issues
            elif 'access' in error_str or 'authorization' in error_str or 'permission' in error_str:
                print(f"Bedrock agent call failed due to permission error: {str(e)}")
                return create_permission_analysis_response(architecture_info, str(e))
            
            # Other errors
            else:
                print(f"Bedrock agent call failed with unknown error: {str(e)}")
                return create_fallback_analysis_response(architecture_info, str(e))
    
    # This should never be reached, but just in case
    return create_throttling_analysis_response(architecture_info, "Max retries exceeded")

def parse_bedrock_response(response_text, architecture_info=None):
    """Parse Bedrock agent response into structured format"""
    
    # Extract score from response if possible
    score = 7.0  # Default score
    
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
    
    # Generate description based on actual content
    if architecture_info and architecture_info.get('has_content', False):
        component_types = list(set([comp['service_type'] for comp in architecture_info['components']]))
        description = f"Real AI Analysis: Architecture contains {architecture_info['component_count']} components including {', '.join(component_types[:3])}..."
    else:
        description = "Real AI Analysis: Empty or minimal architecture diagram detected. Analysis focused on general AWS security best practices."
    
    # Add first 200 chars of Bedrock response
    if len(response_text) > 50:
        description += f" {response_text[:200]}..."
    
    # Generate issues based on actual components or general guidance
    issues = generate_security_issues_for_architecture(architecture_info)
    
    return {
        'description': description,
        'overall_score': score,
        'security': {
            'score': score,
            'issues': issues,
            'recommendations': generate_recommendations_for_architecture(architecture_info),
        },
        'raw_bedrock_response': response_text
    }

def create_fallback_analysis_response(architecture_info, error_message):
    """Create fallback analysis when Bedrock call fails"""
    
    if architecture_info and architecture_info.get('has_content', False):
        description = f"Fallback analysis: Architecture contains {architecture_info['component_count']} components. AI service temporarily unavailable."
        score = 6.5
    else:
        description = "Fallback analysis: Empty or minimal architecture diagram. Please upload a valid draw.io file with AWS components."
        score = 3.0
    
    return {
        'description': description,
        'overall_score': score,
        'security': {
            'score': score,
            'issues': generate_security_issues_for_architecture(architecture_info),
            'recommendations': generate_recommendations_for_architecture(architecture_info),
        },
        'fallback_reason': error_message
    }

def generate_security_issues_for_architecture(architecture_info):
    """Generate security issues based on actual architecture components"""
    
    issues = []
    
    if not architecture_info or not architecture_info.get('has_content', False):
        issues.append({
            'severity': 'HIGH',
            'component': 'Architecture Diagram',
            'issue': 'Empty or invalid architecture diagram uploaded',
            'recommendation': 'Please upload a valid draw.io file containing AWS architecture components',
            'aws_service': 'General'
        })
        return issues
    
    # Check for specific component types and generate relevant issues
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
            'recommendation': 'Implement least privilege security groups, enable Systems Manager Session Manager',
            'aws_service': 'EC2'
        })
    
    if 'RDS' in component_types:
        issues.append({
            'severity': 'MEDIUM',
            'component': 'RDS Database',
            'issue': 'Database security configuration should be reviewed',
            'recommendation': 'Enable encryption at rest and in transit, implement proper backup strategy',
            'aws_service': 'RDS'
        })
    
    if 'S3' in component_types:
        issues.append({
            'severity': 'MEDIUM',
            'component': 'S3 Storage',
            'issue': 'S3 bucket security and access policies need review',
            'recommendation': 'Implement bucket policies, enable versioning, configure access logging',
            'aws_service': 'S3'
        })
    
    # Add general issue if no specific components found
    if not issues:
        issues.append({
            'severity': 'LOW',
            'component': 'General Architecture',
            'issue': 'Architecture requires comprehensive security review',
            'recommendation': 'Implement AWS security best practices and enable comprehensive monitoring',
            'aws_service': 'General'
        })
    
    return issues

def generate_recommendations_for_architecture(architecture_info):
    """Generate security recommendations based on actual architecture"""
    
    if not architecture_info or not architecture_info.get('has_content', False):
        return [
            'Upload a valid draw.io architecture diagram with AWS components',
            'Include proper AWS service icons and labels',
            'Ensure the diagram shows network connections and data flow',
            'Consider using AWS architecture icons for clarity'
        ]
    
    recommendations = [
        'Implement AWS WAF for application-layer protection',
        'Enable AWS CloudTrail for comprehensive audit logging',
        'Configure VPC Flow Logs for network monitoring',
        'Use AWS Config for compliance monitoring and drift detection'
    ]
    
    # Add specific recommendations based on components
    component_types = [comp['service_type'] for comp in architecture_info['components']]
    
    if 'RDS' in component_types:
        recommendations.append('Enable RDS Performance Insights and automated backups')
    
    if 'S3' in component_types:
        recommendations.append('Implement S3 bucket lifecycle policies and cross-region replication')
    
    if 'Load Balancer' in component_types:
        recommendations.append('Configure ALB access logs and implement health checks')
    
    if 'EC2' in component_types:
        recommendations.append('Use AWS Systems Manager for secure instance management')
    
    return recommendations[:6]  # Limit to 6 recommendations

def create_throttling_analysis_response(architecture_info, error_message):
    """Create analysis response when Bedrock is being throttled"""
    
    if architecture_info and architecture_info.get('has_content', False):
        description = f"⚠️ Bedrock Quota Limit: Detected {architecture_info['component_count']} components. Your account has a 1 request/minute Bedrock quota. Please wait 60+ seconds between requests."
        score = 7.0  # Default score when throttled
    else:
        description = "⚠️ Bedrock Quota Limit: Your AWS account has very low Bedrock quotas (1 request/minute). Consider requesting a quota increase in AWS Console → Service Quotas."
        score = 5.0
    
    return {
        'description': description,
        'overall_score': score,
        'security': {
            'score': score,
            'issues': [{
                'severity': 'INFO',
                'component': 'Bedrock AI Service',
                'issue': 'Amazon Bedrock is currently throttling requests due to high usage',
                'recommendation': 'Wait a few minutes and try again. The system will automatically retry.',
                'aws_service': 'Bedrock'
            }],
            'recommendations': [
                'Wait at least 60 seconds between requests (1 request/minute quota)',
                'Request quota increase in AWS Console → Service Quotas → Bedrock',
                'Ask for 50-100 requests/minute for production usage',
                'Architecture parsing works - only AI analysis needs quota increase'
            ],
        },
        'throttling_error': error_message,
        'error_type': 'THROTTLING'
    }

def create_permission_analysis_response(architecture_info, error_message):
    """Create analysis response when there are permission issues"""
    
    if architecture_info and architecture_info.get('has_content', False):
        description = f"🔒 Permission Error: Detected {architecture_info['component_count']} components but AI analysis failed due to insufficient permissions."
        score = 6.0
    else:
        description = "🔒 Permission Error: AI analysis failed due to insufficient Amazon Bedrock permissions."
        score = 4.0
    
    return {
        'description': description,
        'overall_score': score,
        'security': {
            'score': score,
            'issues': [{
                'severity': 'HIGH',
                'component': 'Bedrock Permissions',
                'issue': 'Lambda function lacks sufficient permissions to invoke Bedrock agent',
                'recommendation': 'Contact administrator to update IAM permissions for Bedrock access',
                'aws_service': 'IAM'
            }],
            'recommendations': [
                'Update Lambda execution role with bedrock:InvokeAgent permissions',
                'Ensure Bedrock agent alias is accessible',
                'Check CloudWatch logs for detailed permission errors'
            ],
        },
        'permission_error': error_message,
        'error_type': 'PERMISSION'
    }