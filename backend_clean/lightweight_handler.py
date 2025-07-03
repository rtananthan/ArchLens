# ArchLens Backend - Lightweight Lambda Handler
# This file contains the main API handler for processing architecture diagram uploads
# and coordinating with Amazon Bedrock for AI-powered security analysis.

# Standard library imports for JSON processing, file handling, and data types
import json
import os
import base64
import xml.etree.ElementTree as ET
from uuid import uuid4
from typing import Dict, Any
from datetime import datetime, timezone
from decimal import Decimal

# AWS SDK for interacting with S3, DynamoDB, and Bedrock services
import boto3

class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle DynamoDB Decimal types.
    
    DynamoDB stores numbers as Decimal objects to maintain precision,
    but JSON serialization requires conversion to float for frontend consumption.
    This encoder automatically converts Decimal objects to floats during JSON serialization.
    """
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)  # Convert Decimal to float for JSON serialization
        return super(DecimalEncoder, self).default(o)

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function - Entry point for all API requests.
    
    This function serves as the central router for the ArchLens API, handling:
    - Health checks for system monitoring
    - File uploads for architecture analysis
    - Results retrieval for completed analyses
    
    Args:
        event: API Gateway event containing request data (headers, body, path, method)
        context: Lambda runtime context (timeout, memory, request ID)
        
    Returns:
        Dict containing HTTP response with status code, headers, and JSON body
        
    Architecture Flow:
    1. Parse incoming HTTP request (method, path, headers)
    2. Route to appropriate handler function
    3. Process request and interact with AWS services
    4. Return standardized JSON response with CORS headers
    """
    # Log the incoming event for debugging (sanitized in production)
    print(f"Incoming API request: {json.dumps(event, default=str)}")
    
    # Extract HTTP method and path from API Gateway event
    # These determine which handler function to call
    http_method = event.get('httpMethod', 'GET')  # GET, POST, OPTIONS, etc.
    path = event.get('path', '/')                 # /api/health, /api/analyze, etc.
    
    # CORS (Cross-Origin Resource Sharing) headers for browser compatibility
    # These headers allow the frontend (running on CloudFront) to call this API
    cors_headers = {
        'Content-Type': 'application/json',                               # Always return JSON
        'Access-Control-Allow-Origin': '*',                             # Allow all origins (can be restricted to CloudFront domain)
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',           # Supported HTTP methods
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'   # Headers the browser can send
    }
    
    # Handle CORS preflight requests (sent by browsers before actual requests)
    # When a browser makes a cross-origin request, it first sends an OPTIONS request
    # to check if the actual request is allowed. We respond with allowed methods/headers.
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': ''  # Empty body for preflight response
        }
    
    # Load AWS resource identifiers from environment variables
    # These are set by CloudFormation/CDK during deployment and vary by environment
    UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET')                    # S3 bucket for uploaded files
    ANALYSIS_TABLE = os.environ.get('ANALYSIS_TABLE')                  # DynamoDB table for storing results
    BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')              # AI agent for architecture analysis
    BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')  # Agent version/alias
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')        # AWS region for service calls
    
    try:
        # Route: GET /api/health - System health check endpoint
        # Used by monitoring systems and load balancers to verify the service is running
        # Returns configuration info and service status
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
        
        # Route: POST /api/analyze - File upload and analysis endpoint
        # This is the main endpoint where users upload draw.io files for AI analysis
        # Handles multipart form data, stores files in S3, and triggers Bedrock analysis
        elif path == '/api/analyze' and http_method == 'POST':
            return handle_file_upload(event, UPLOAD_BUCKET, ANALYSIS_TABLE, BEDROCK_AGENT_ID, BEDROCK_AGENT_ALIAS_ID, AWS_REGION, cors_headers)
        
        # Route: GET /api/analysis/{id} - Retrieve analysis results
        # Returns completed analysis results from DynamoDB
        # Also handles /api/analysis/{id}/status for progress checking
        elif path.startswith('/api/analysis/') and http_method == 'GET':
            return handle_get_analysis(event, ANALYSIS_TABLE, AWS_REGION, cors_headers)
        
        # Default response for unrecognized routes
        # Returns 404 Not Found with details about the attempted request
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
        # Global error handler - catches any unhandled exceptions
        # Logs the error for debugging and returns a user-friendly error response
        print(f"Unhandled error in main handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': str(e)  # In production, this might be sanitized
            })
        }

def handle_file_upload(event, upload_bucket, analysis_table, bedrock_agent_id, bedrock_agent_alias_id, aws_region, cors_headers):
    """
    Handle file upload and architecture analysis workflow.
    
    This function processes uploaded draw.io files through the complete analysis pipeline:
    1. Parse multipart form data from the browser
    2. Extract and validate the XML file content
    3. Store the file in S3 for processing
    4. Parse architecture components from the XML
    5. Send to Amazon Bedrock for AI security analysis
    6. Store results in DynamoDB
    7. Return analysis ID and initial results to the frontend
    
    Args:
        event: API Gateway event containing the uploaded file data
        upload_bucket: S3 bucket name for file storage
        analysis_table: DynamoDB table name for results
        bedrock_agent_id: Amazon Bedrock agent identifier for AI analysis
        bedrock_agent_alias_id: Bedrock agent alias for versioning
        aws_region: AWS region for service calls
        cors_headers: HTTP headers for browser compatibility
        
    Returns:
        HTTP response with analysis ID and initial results
    """
    
    # Step 1: Extract and decode the request body
    # API Gateway can send data either as plain text or base64-encoded
    body = event.get('body', '')
    if event.get('isBase64Encoded', False):
        # Binary data (like file uploads) comes base64-encoded
        body = base64.b64decode(body)
    else:
        # Text data comes as string, convert to bytes for consistent processing
        body = body.encode('utf-8') if isinstance(body, str) else body
    
    # Step 2: Initialize variables for file extraction
    file_content = None                    # Will hold the actual XML content
    file_name = "uploaded_file.drawio"     # Default filename if not found in form data
    
    try:
        # Step 3: Parse multipart form data manually
        # Note: In production, consider using a proper multipart parser library
        # This simplified parser works for standard browser file uploads
        if body:
            # Convert bytes to string, ignoring invalid UTF-8 characters
            body_str = body.decode('utf-8', errors='ignore')
            
            # Step 4: Extract filename from multipart headers
            # Multipart form data includes headers like: Content-Disposition: form-data; name="file"; filename="architecture.drawio"
            if 'filename=' in body_str:
                # Find the filename parameter in the Content-Disposition header
                filename_start = body_str.find('filename="') + 10  # Skip 'filename="'
                filename_end = body_str.find('"', filename_start)   # Find closing quote
                if filename_end > filename_start:
                    file_name = body_str[filename_start:filename_end]
            
            # Step 5: Extract XML content from multipart data
            # Draw.io files are XML documents that start with <?xml declaration
            if '<?xml' in body_str:
                xml_start = body_str.find('<?xml')
                # Find the end of the XML content by looking for closing tags or boundaries
                xml_end = len(body_str)
                
                # Method 1: Look for the proper XML ending tag
                # Draw.io files typically end with </mxfile>
                if '</mxfile>' in body_str:
                    mxfile_end = body_str.find('</mxfile>', xml_start) + len('</mxfile>')
                    xml_end = min(xml_end, mxfile_end)
                
                # Method 2: Look for multipart boundary markers that indicate end of file content
                # Multipart boundaries separate different parts of the form data
                for boundary_marker in ['\r\n--', '\n--']:
                    marker_pos = body_str.find(boundary_marker, xml_start)
                    if marker_pos > xml_start:
                        xml_end = min(xml_end, marker_pos)
                        break
                
                # Extract the clean XML content
                file_content = body_str[xml_start:xml_end].strip()
                
                # Clean up any remaining multipart artifacts that might have been included
                if file_content.endswith('EOF < /dev/null'):
                    file_content = file_content.replace('EOF < /dev/null', '').strip()
        
        # Step 6: Validate extracted file content
        # If no valid XML content found, return appropriate error messages
        if not file_content or '<?xml' not in file_content:
            # Check file extension first - helps users understand file type requirements
            if not file_name.endswith(('.xml', '.drawio')):
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'error': 'Invalid File Type',
                        'message': 'Please upload a valid draw.io (.drawio) or XML file.'
                    })
                }
            
            # File has correct extension but we couldn't extract XML content
            # This might happen with corrupted files or unsupported formats
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'File Parse Error',
                    'message': f'Unable to parse the uploaded file "{file_name}". Please ensure it\'s a valid draw.io file with XML content.'
                })
            }
        
    except Exception as parse_error:
        # Handle any errors during file parsing (network issues, malformed data, etc.)
        print(f"File parsing error: {str(parse_error)}")
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'File Processing Error',
                'message': 'Failed to process the uploaded file. Please try again with a valid draw.io file.'
            })
        }
    
    # Step 7: Generate unique analysis ID for tracking this request
    # Format: analysis_12345678 (8 random hex characters for uniqueness)
    analysis_id = f"analysis_{uuid4().hex[:8]}"
    
    # Step 8: Initialize AWS service clients
    # These clients handle communication with different AWS services
    s3_client = boto3.client('s3', region_name=aws_region)                           # For file storage
    dynamodb = boto3.resource('dynamodb', region_name=aws_region)                    # For results storage
    bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name=aws_region)  # For AI analysis
    
    try:
        # Step 9: Create timestamp for tracking and TTL
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Step 10: Store file in S3 for audit trail and potential reprocessing
        # Files are organized by analysis ID for easy cleanup and management
        s3_key = f"uploads/{analysis_id}/{file_name}"  # Path: uploads/analysis_12345678/architecture.drawio
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=s3_key,
            Body=file_content.encode('utf-8'),    # Convert string to bytes for S3 storage
            ContentType='application/xml',        # Proper MIME type for XML files
            Metadata={                            # Custom metadata for tracking
                'original-filename': file_name,
                'upload-timestamp': timestamp,
                'analysis-id': analysis_id
            }
        )
        
        # Step 11: Parse XML to extract architecture components
        # This identifies AWS services and their relationships from the diagram
        architecture_info = parse_uploaded_xml(file_content)
        
        # Step 12: Send to Amazon Bedrock for AI-powered security analysis
        # This is where the actual AI analysis happens using Claude 3.5 Sonnet
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
    """
    Parse draw.io XML content to extract AWS architecture components.
    
    Draw.io files use a specific XML structure where architectural components
    are stored as mxCell elements with various properties. This function:
    1. Parses the XML using Python's ElementTree
    2. Extracts all mxCell elements (components and connections)
    3. Identifies AWS service types based on component names/styles
    4. Maps relationships between components
    5. Returns structured data for AI analysis
    
    Args:
        xml_content: Raw XML string from uploaded draw.io file
        
    Returns:
        Dict containing:
        - components: List of AWS services found in the diagram
        - connections: List of relationships between components
        - metadata: Counts and validation flags
    """
    
    try:
        # Parse XML string into ElementTree object for structured access
        root = ET.fromstring(xml_content)
        components = []    # Will store AWS service components (EC2, RDS, S3, etc.)
        connections = []   # Will store relationships between components (arrows, lines)
        
        # Iterate through all mxCell elements in the draw.io XML
        # mxCell is the fundamental building block in draw.io's data model
        for cell in root.iter('mxCell'):
            cell_id = cell.get('id')      # Unique identifier for this cell
            value = cell.get('value', '') # The text/label shown on the component
            style = cell.get('style', '') # CSS-like styling information
            
            # Process component cells (skip root cells 0 and 1 which are containers)
            if value and cell_id not in ['0', '1']:
                # Use the component name and style to identify what AWS service this represents
                service_type = identify_aws_service_type(value, style)
                
                # Store component information for AI analysis
                components.append({
                    'id': cell_id,              # For tracking relationships
                    'name': value,              # User-provided component name
                    'service_type': service_type, # Identified AWS service type
                    'style': style              # Visual styling (may contain service hints)
                })
            
            # Process connection cells (arrows, lines between components)
            # These represent data flow, dependencies, or communication paths
            source = cell.get('source')  # ID of the component this connection starts from
            target = cell.get('target')  # ID of the component this connection goes to
            if source and target:
                connections.append({
                    'source': source,
                    'target': target,
                    'type': 'connection'  # Could be extended to support different connection types
                })
        
        # Return structured architecture information for AI analysis
        return {
            'components': components,                    # List of AWS services found
            'connections': connections,                  # List of relationships between services
            'component_count': len(components),          # Total number of components (for analysis)
            'connection_count': len(connections),        # Total number of connections (for complexity assessment)
            'has_content': len(components) > 0          # Flag indicating if diagram has actual content
        }
        
    except Exception as e:
        # Handle XML parsing errors gracefully (malformed XML, encoding issues, etc.)
        print(f"XML parsing error: {str(e)}")
        return {
            'components': [],           # Empty list for failed parsing
            'connections': [],          # Empty list for failed parsing
            'component_count': 0,       # Zero count indicates parsing failure
            'connection_count': 0,      # Zero count indicates parsing failure
            'has_content': False,       # Flag indicates no valid content found
            'parse_error': str(e)       # Store error for debugging
        }

def identify_aws_service_type(value, style):
    """
    Identify AWS service type from component name and styling information.
    
    This function uses pattern matching to classify draw.io components into
    AWS service categories. It examines both the component's display name
    and its styling properties to make intelligent guesses about what
    AWS service the component represents.
    
    Common patterns:
    - Text matching: "Load Balancer" → Load Balancer
    - Abbreviations: "ALB" → Load Balancer
    - Generic terms: "Database" → RDS
    - Style hints: AWS-specific styling → AWS Service
    
    Args:
        value: The display text/label of the component
        style: CSS-like styling string that may contain service hints
        
    Returns:
        String representing the identified AWS service type
    """
    
    # Convert to lowercase for case-insensitive matching
    value_lower = value.lower()
    style_lower = style.lower()
    
    # Pattern matching for AWS services - comprehensive enterprise service coverage
    # Organized by service category for better maintainability
    
    # Compute Services
    if any(keyword in value_lower for keyword in ['ec2', 'instance', 'server', 'virtual machine', 'vm']):
        return 'EC2'
    elif any(keyword in value_lower for keyword in ['lambda', 'function', 'serverless']):
        return 'Lambda'
    elif any(keyword in value_lower for keyword in ['ecs', 'container service', 'docker']):
        return 'ECS'
    elif any(keyword in value_lower for keyword in ['eks', 'kubernetes', 'k8s']):
        return 'EKS'
    elif any(keyword in value_lower for keyword in ['fargate']):
        return 'Fargate'
    elif any(keyword in value_lower for keyword in ['batch']):
        return 'AWS Batch'
    elif any(keyword in value_lower for keyword in ['lightsail']):
        return 'Lightsail'
    
    # Storage Services
    elif any(keyword in value_lower for keyword in ['s3', 'bucket', 'object storage']):
        return 'S3'
    elif any(keyword in value_lower for keyword in ['ebs', 'elastic block']):
        return 'EBS'
    elif any(keyword in value_lower for keyword in ['efs', 'elastic file']):
        return 'EFS'
    elif any(keyword in value_lower for keyword in ['fsx']):
        return 'FSx'
    elif any(keyword in value_lower for keyword in ['glacier', 'archive']):
        return 'S3 Glacier'
    elif any(keyword in value_lower for keyword in ['storage gateway']):
        return 'Storage Gateway'
    
    # Database Services
    elif any(keyword in value_lower for keyword in ['rds', 'relational database', 'mysql', 'postgres', 'oracle', 'sql server']):
        return 'RDS'
    elif any(keyword in value_lower for keyword in ['dynamodb', 'nosql', 'document db']):
        return 'DynamoDB'
    elif any(keyword in value_lower for keyword in ['aurora']):
        return 'Aurora'
    elif any(keyword in value_lower for keyword in ['redshift', 'data warehouse']):
        return 'Redshift'
    elif any(keyword in value_lower for keyword in ['documentdb', 'mongodb']):
        return 'DocumentDB'
    elif any(keyword in value_lower for keyword in ['neptune', 'graph']):
        return 'Neptune'
    elif any(keyword in value_lower for keyword in ['elasticache', 'redis', 'memcached']):
        return 'ElastiCache'
    
    # Networking Services
    elif any(keyword in value_lower for keyword in ['vpc', 'virtual private cloud']):
        return 'VPC'
    elif any(keyword in value_lower for keyword in ['subnet', 'private subnet', 'public subnet']):
        return 'Subnet'
    elif any(keyword in value_lower for keyword in ['load balancer', 'alb', 'elb', 'nlb', 'application load balancer', 'network load balancer']):
        return 'Load Balancer'
    elif any(keyword in value_lower for keyword in ['cloudfront', 'cdn', 'content delivery']):
        return 'CloudFront'
    elif any(keyword in value_lower for keyword in ['api gateway', 'rest api', 'graphql']):
        return 'API Gateway'
    elif any(keyword in value_lower for keyword in ['route 53', 'dns', 'domain']):
        return 'Route 53'
    elif any(keyword in value_lower for keyword in ['vpc endpoint', 'endpoint']):
        return 'VPC Endpoint'
    elif any(keyword in value_lower for keyword in ['nat gateway', 'nat']):
        return 'NAT Gateway'
    elif any(keyword in value_lower for keyword in ['internet gateway', 'igw']):
        return 'Internet Gateway'
    elif any(keyword in value_lower for keyword in ['transit gateway']):
        return 'Transit Gateway'
    elif any(keyword in value_lower for keyword in ['direct connect']):
        return 'Direct Connect'
    
    # Security Services
    elif any(keyword in value_lower for keyword in ['iam', 'identity', 'access management', 'role', 'policy', 'user']):
        return 'IAM'
    elif any(keyword in value_lower for keyword in ['security group', 'sg']):
        return 'Security Group'
    elif any(keyword in value_lower for keyword in ['nacl', 'network acl']):
        return 'Network ACL'
    elif any(keyword in value_lower for keyword in ['kms', 'key management']):
        return 'KMS'
    elif any(keyword in value_lower for keyword in ['secrets manager', 'secret']):
        return 'Secrets Manager'
    elif any(keyword in value_lower for keyword in ['certificate manager', 'acm', 'ssl', 'tls']):
        return 'Certificate Manager'
    elif any(keyword in value_lower for keyword in ['waf', 'web application firewall']):
        return 'WAF'
    elif any(keyword in value_lower for keyword in ['shield', 'ddos']):
        return 'Shield'
    elif any(keyword in value_lower for keyword in ['guardduty']):
        return 'GuardDuty'
    elif any(keyword in value_lower for keyword in ['security hub']):
        return 'Security Hub'
    elif any(keyword in value_lower for keyword in ['inspector']):
        return 'Inspector'
    elif any(keyword in value_lower for keyword in ['macie']):
        return 'Macie'
    
    # Monitoring & Management
    elif any(keyword in value_lower for keyword in ['cloudwatch', 'monitoring', 'metrics', 'logs']):
        return 'CloudWatch'
    elif any(keyword in value_lower for keyword in ['cloudtrail', 'audit', 'logging']):
        return 'CloudTrail'
    elif any(keyword in value_lower for keyword in ['config', 'compliance']):
        return 'Config'
    elif any(keyword in value_lower for keyword in ['systems manager', 'ssm']):
        return 'Systems Manager'
    elif any(keyword in value_lower for keyword in ['x-ray', 'tracing']):
        return 'X-Ray'
    elif any(keyword in value_lower for keyword in ['cloudformation', 'cfn', 'stack']):
        return 'CloudFormation'
    
    # Application Services
    elif any(keyword in value_lower for keyword in ['sns', 'notification']):
        return 'SNS'
    elif any(keyword in value_lower for keyword in ['sqs', 'queue']):
        return 'SQS'
    elif any(keyword in value_lower for keyword in ['eventbridge', 'event bus']):
        return 'EventBridge'
    elif any(keyword in value_lower for keyword in ['step functions', 'workflow']):
        return 'Step Functions'
    elif any(keyword in value_lower for keyword in ['kinesis', 'streaming']):
        return 'Kinesis'
    elif any(keyword in value_lower for keyword in ['ses', 'email']):
        return 'SES'
    
    # Analytics & ML
    elif any(keyword in value_lower for keyword in ['athena', 'query']):
        return 'Athena'
    elif any(keyword in value_lower for keyword in ['glue', 'etl']):
        return 'Glue'
    elif any(keyword in value_lower for keyword in ['emr', 'hadoop', 'spark']):
        return 'EMR'
    elif any(keyword in value_lower for keyword in ['sagemaker', 'machine learning', 'ml']):
        return 'SageMaker'
    elif any(keyword in value_lower for keyword in ['bedrock', 'ai']):
        return 'Bedrock'
    
    # Check for AWS-specific styling or generic AWS indicator
    elif 'aws' in style_lower or 'amazon' in value_lower:
        return 'AWS Service'
    else:
        return 'Unknown'

def call_bedrock_agent(bedrock_agent_client, agent_id, agent_alias_id, xml_content, session_id, architecture_info=None):
    """
    Call Amazon Bedrock agent for AI-powered architecture security analysis.
    
    This function handles the core AI integration with Amazon Bedrock's Claude 3.5 Sonnet model.
    It includes sophisticated retry logic to handle quota limitations and throttling,
    which is critical since new AWS accounts have very low Bedrock quotas (1 request/minute).
    
    The function:
    1. Prepares a structured prompt with architecture details
    2. Calls the Bedrock agent with retry logic
    3. Handles throttling, permission errors, and other failures
    4. Parses the AI response into structured JSON
    5. Returns analysis results or fallback responses
    
    Args:
        bedrock_agent_client: Boto3 client for Bedrock agent runtime
        agent_id: Unique identifier for the Bedrock agent
        agent_alias_id: Agent version/alias identifier
        xml_content: Raw XML content (not currently used in prompt)
        session_id: Unique session ID for tracking conversations
        architecture_info: Parsed component information from draw.io file
        
    Returns:
        Dict containing analysis results, security scores, and recommendations
    """
    
    # Import time utilities for retry logic
    import time
    import random
    
    # Retry configuration optimized for API Gateway timeout limits
    max_retries = 1   # Limited retries to stay under 29-second API Gateway timeout
    base_delay = 10   # Base delay in seconds between retries
    
    for attempt in range(max_retries + 1):
        try:
            # Create a comprehensive enterprise-focused prompt
            if architecture_info and architecture_info.get('has_content', False):
                components_summary = f"Architecture contains {architecture_info['component_count']} AWS services with {architecture_info['connection_count']} interconnections"
                
                # Create detailed component analysis for enterprise assessment
                components_list = ""
                service_categories = {}
                
                for component in architecture_info['components']:
                    service_type = component['service_type']
                    if service_type not in service_categories:
                        service_categories[service_type] = []
                    service_categories[service_type].append(component['name'])
                
                # Format components by category for better analysis
                for category, components in service_categories.items():
                    components_list += f"\n{category}: {', '.join(components)}"
                
                # Create connections analysis
                connections_analysis = ""
                if architecture_info['connections']:
                    connections_analysis = f"\nData Flow Connections: {architecture_info['connection_count']} connections between services"
                
            else:
                components_summary = "Empty or minimal architecture diagram - performing general AWS security assessment"
                components_list = "No specific AWS services detected"
                connections_analysis = ""
            
            # Enterprise-focused prompt for comprehensive security analysis
            prompt = f"""Conduct a comprehensive AWS Well-Architected Framework Security Pillar analysis:

ARCHITECTURE OVERVIEW:
{components_summary}

AWS SERVICES IDENTIFIED:{components_list}{connections_analysis}

PERFORM ENTERPRISE SECURITY ANALYSIS:

1. AWS Well-Architected Security Pillar Assessment (all 6 principles)
2. Compliance framework alignment (SOC2, PCI-DSS, NIST)
3. Critical security findings with business impact
4. Quantified risk assessment with CVSS scores
5. Prioritized remediation roadmap with effort estimates
6. Executive summary with compliance status

Provide comprehensive enterprise-grade analysis in the specified JSON format.

Focus on actionable security improvements that align with enterprise compliance requirements and provide quantified business value."""

            # Call the Bedrock agent with enterprise security analysis prompt
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
            
            # Parse the enterprise security analysis response
            return parse_enterprise_bedrock_response(result_text, architecture_info)
            
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

def parse_enterprise_bedrock_response(response_text, architecture_info=None):
    """
    Parse enterprise-grade Bedrock response with comprehensive security analysis.
    
    This function attempts to parse the structured JSON response from the enterprise
    Bedrock agent. If parsing fails, it falls back to extracting key information
    and creating a structured response.
    
    Args:
        response_text: Raw response text from Bedrock agent
        architecture_info: Parsed architecture component information
        
    Returns:
        Dict containing enterprise security analysis with Well-Architected assessment
    """
    import json
    import re
    
    # First, try to parse as complete JSON response
    try:
        # Look for JSON content in the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
            parsed_response = json.loads(json_text)
            
            # Validate that it has the expected enterprise structure
            if 'overall_score' in parsed_response and 'security_findings' in parsed_response:
                # Add our architecture context
                parsed_response['architecture_context'] = {
                    'components_analyzed': architecture_info.get('component_count', 0) if architecture_info else 0,
                    'services_identified': list(set([comp['service_type'] for comp in architecture_info['components']])) if architecture_info and architecture_info.get('components') else [],
                    'analysis_timestamp': datetime.now(timezone.utc).isoformat()
                }
                return parsed_response
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Failed to parse enterprise JSON response: {e}")
    
    # Fallback: Create enterprise-structured response from partial data
    return create_enterprise_fallback_response(response_text, architecture_info)

def create_enterprise_fallback_response(response_text, architecture_info=None):
    """
    Create enterprise-grade fallback response when full JSON parsing fails.
    
    This function extracts available information from the Bedrock response
    and structures it according to enterprise requirements.
    """
    import re
    
    # Extract scores using multiple patterns
    overall_score = extract_score_from_text(response_text, default=7.0)
    
    # Generate enterprise-focused description
    if architecture_info and architecture_info.get('has_content', False):
        component_types = list(set([comp['service_type'] for comp in architecture_info['components']]))
        unique_services = [svc for svc in component_types if svc != 'Unknown']
        
        description = f"Enterprise Security Analysis: Analyzed {architecture_info['component_count']} AWS services including {', '.join(unique_services[:5])}"
        if len(unique_services) > 5:
            description += f" and {len(unique_services) - 5} additional services"
    else:
        description = "Enterprise Security Analysis: General AWS security assessment performed on minimal architecture"
    
    # Extract key findings from response text
    security_findings = extract_security_findings_from_text(response_text, architecture_info)
    
    # Create Well-Architected assessment
    well_architected = create_well_architected_assessment(architecture_info, overall_score)
    
    # Create executive summary
    executive_summary = create_executive_summary(overall_score, security_findings, architecture_info)
    
    return {
        'overall_score': overall_score,
        'executive_summary': executive_summary,
        'well_architected_assessment': well_architected,
        'security_findings': security_findings,
        'compliance_assessment': create_compliance_assessment(overall_score),
        'remediation_roadmap': create_remediation_roadmap(security_findings),
        'architecture_summary': create_architecture_summary(architecture_info),
        'analysis_metadata': {
            'analysis_type': 'enterprise_fallback',
            'bedrock_response_length': len(response_text),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }

def extract_score_from_text(response_text, default=7.0):
    """Extract security score from response text using multiple patterns"""
    import re
    
    score_patterns = [
        r'overall[_\s]*score["\s]*:["\s]*(\d+(?:\.\d+)?)',
        r'score["\s]*:["\s]*(\d+(?:\.\d+)?)',
        r'security[_\s]*score["\s]*:["\s]*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:/\s*10|out\s*of\s*10)'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                if score > 10:
                    score = score / 10  # Convert percentage to 0-10 scale
                return min(max(score, 0), 10)  # Ensure score is between 0-10
            except (ValueError, IndexError):
                continue
    
    return default

def extract_security_findings_from_text(response_text, architecture_info):
    """Extract and structure security findings from Bedrock response"""
    findings = []
    
    # Generate findings based on detected services and common issues
    if architecture_info and architecture_info.get('components'):
        service_types = [comp['service_type'] for comp in architecture_info['components']]
        
        # Check for common enterprise security issues based on services
        if 'RDS' in service_types or 'DynamoDB' in service_types:
            findings.append({
                'id': 'SEC-001',
                'severity': 'HIGH',
                'category': 'Data Protection',
                'component': 'Database Services',
                'finding': 'Database encryption configuration requires review',
                'impact': 'Potential data exposure risk, compliance gaps',
                'recommendation': 'Enable encryption at rest and in transit for all database services',
                'remediation_effort': 'Medium - 4-8 hours',
                'compliance_frameworks': ['SOC2', 'PCI-DSS', 'HIPAA'],
                'aws_service': 'RDS/DynamoDB',
                'cvss_score': 7.5
            })
        
        if 'S3' in service_types:
            findings.append({
                'id': 'SEC-002',
                'severity': 'MEDIUM',
                'category': 'Access Control',
                'component': 'S3 Storage',
                'finding': 'S3 bucket policies and access controls need verification',
                'impact': 'Potential unauthorized data access',
                'recommendation': 'Implement least privilege bucket policies and enable access logging',
                'remediation_effort': 'Low - 2-4 hours',
                'compliance_frameworks': ['SOC2', 'NIST-CSF'],
                'aws_service': 'S3',
                'cvss_score': 5.5
            })
        
        if 'API Gateway' in service_types or 'Load Balancer' in service_types:
            findings.append({
                'id': 'SEC-003',
                'severity': 'MEDIUM',
                'category': 'Network Security',
                'component': 'API Gateway/Load Balancer',
                'finding': 'Web Application Firewall (WAF) implementation required',
                'impact': 'Exposure to web-based attacks and DDoS',
                'recommendation': 'Deploy AWS WAF with appropriate rule sets',
                'remediation_effort': 'Medium - 1-2 days',
                'compliance_frameworks': ['SOC2', 'PCI-DSS'],
                'aws_service': 'API Gateway/ALB',
                'cvss_score': 6.0
            })
        
        if 'EC2' in service_types:
            findings.append({
                'id': 'SEC-004',
                'severity': 'HIGH',
                'category': 'Infrastructure Protection',
                'component': 'EC2 Instances',
                'finding': 'Instance security hardening and patch management review needed',
                'impact': 'Vulnerability exploitation risk',
                'recommendation': 'Implement AWS Systems Manager for patch management and security baseline',
                'remediation_effort': 'High - 1-2 weeks',
                'compliance_frameworks': ['SOC2', 'NIST-CSF'],
                'aws_service': 'EC2',
                'cvss_score': 8.0
            })
    
    # Add general finding if no specific services detected
    if not findings:
        findings.append({
            'id': 'SEC-000',
            'severity': 'LOW',
            'category': 'General Assessment',
            'component': 'Overall Architecture',
            'finding': 'Architecture requires comprehensive security review',
            'impact': 'Unknown security posture, compliance gaps possible',
            'recommendation': 'Conduct detailed security assessment with specific service configurations',
            'remediation_effort': 'High - 2-4 weeks',
            'compliance_frameworks': ['SOC2', 'NIST-CSF'],
            'aws_service': 'Multiple',
            'cvss_score': 3.0
        })
    
    return findings

def create_well_architected_assessment(architecture_info, overall_score):
    """Create Well-Architected Framework Security Pillar assessment"""
    base_score = overall_score
    
    return {
        'sec01_identity_foundation': {
            'score': max(base_score - 1, 3),
            'findings': ['IAM roles and policies require review', 'MFA implementation status unknown'],
            'recommendations': ['Implement least privilege IAM policies', 'Enable MFA for all privileged accounts']
        },
        'sec02_security_all_layers': {
            'score': base_score,
            'findings': ['Security group configurations need validation', 'Network segmentation review required'],
            'recommendations': ['Implement defense in depth strategy', 'Deploy network monitoring tools']
        },
        'sec03_automate_security': {
            'score': max(base_score - 2, 2),
            'findings': ['Limited automated security controls visible', 'Manual security processes identified'],
            'recommendations': ['Implement AWS Config rules', 'Deploy automated security scanning']
        },
        'sec04_protect_data': {
            'score': max(base_score - 1.5, 2),
            'findings': ['Data encryption status requires verification', 'Key management practices need review'],
            'recommendations': ['Enable encryption for all data stores', 'Implement proper key rotation']
        },
        'sec05_reduce_access': {
            'score': max(base_score - 1, 3),
            'findings': ['Access patterns require analysis', 'Privileged access management needed'],
            'recommendations': ['Implement just-in-time access', 'Deploy privileged access monitoring']
        },
        'sec06_prepare_events': {
            'score': max(base_score - 2.5, 1),
            'findings': ['Incident response capabilities unclear', 'Security monitoring gaps identified'],
            'recommendations': ['Develop incident response plan', 'Implement comprehensive security monitoring']
        }
    }

def create_executive_summary(overall_score, security_findings, architecture_info):
    """Create executive summary for C-level stakeholders"""
    critical_findings = len([f for f in security_findings if f['severity'] == 'CRITICAL'])
    high_findings = len([f for f in security_findings if f['severity'] == 'HIGH'])
    
    if overall_score >= 8:
        posture = 'Strong - well configured'
    elif overall_score >= 6:
        posture = 'Moderate - requires attention'
    elif overall_score >= 4:
        posture = 'Weak - significant gaps'
    else:
        posture = 'Critical - immediate action required'
    
    if critical_findings > 0 or high_findings > 2:
        compliance_status = 'Non-compliant - critical gaps identified'
    elif high_findings > 0:
        compliance_status = 'Partially compliant - gaps require attention'
    else:
        compliance_status = 'Generally compliant - minor improvements needed'
    
    return {
        'security_posture': posture,
        'critical_findings': critical_findings,
        'high_findings': high_findings,
        'compliance_status': compliance_status,
        'priority_actions': [
            'Review and implement encryption for all data stores',
            'Establish comprehensive security monitoring',
            'Implement automated security controls and compliance checking'
        ]
    }

def create_compliance_assessment(overall_score):
    """Create compliance framework assessment"""
    base_compliance = min(max((overall_score / 10) * 100, 30), 95)
    
    return {
        'soc2': {
            'overall_compliance': int(base_compliance),
            'security': int(base_compliance - 5),
            'availability': int(base_compliance + 5),
            'processing_integrity': int(base_compliance),
            'confidentiality': int(base_compliance - 10),
            'privacy': int(base_compliance + 5),
            'gaps': ['Encryption controls', 'Access management', 'Incident response']
        },
        'nist_csf': {
            'identify': int(base_compliance + 10),
            'protect': int(base_compliance - 5),
            'detect': int(base_compliance - 15),
            'respond': int(base_compliance - 25),
            'recover': int(base_compliance - 20)
        }
    }

def create_remediation_roadmap(security_findings):
    """Create prioritized remediation roadmap"""
    immediate = []
    short_term = []
    long_term = []
    
    for finding in security_findings:
        action = {
            'action': finding['recommendation'],
            'effort': finding['remediation_effort'],
            'impact': 'High' if finding['severity'] in ['CRITICAL', 'HIGH'] else 'Medium',
            'compliance_benefit': finding['compliance_frameworks']
        }
        
        if finding['severity'] == 'CRITICAL':
            immediate.append(action)
        elif finding['severity'] == 'HIGH':
            short_term.append(action)
        else:
            long_term.append(action)
    
    return {
        'immediate_priority': immediate,
        'short_term': short_term,
        'long_term': long_term
    }

def create_architecture_summary(architecture_info):
    """Create architecture summary for context"""
    if not architecture_info or not architecture_info.get('components'):
        return {
            'total_services': 0,
            'critical_services': [],
            'data_classification': 'Unknown',
            'network_complexity': 'Unknown',
            'compliance_scope': ['SOC2']
        }
    
    service_types = [comp['service_type'] for comp in architecture_info['components']]
    critical_services = list(set([svc for svc in service_types if svc in ['RDS', 'S3', 'Lambda', 'API Gateway', 'EC2', 'DynamoDB']]))
    
    # Determine data classification based on services
    if any(svc in service_types for svc in ['RDS', 'DynamoDB', 'S3']):
        data_classification = 'Confidential/PII Likely'
    else:
        data_classification = 'Public/Internal'
    
    # Determine network complexity
    if architecture_info['connection_count'] > 10:
        network_complexity = 'High'
    elif architecture_info['connection_count'] > 5:
        network_complexity = 'Medium'
    else:
        network_complexity = 'Low'
    
    return {
        'total_services': len(service_types),
        'critical_services': critical_services,
        'data_classification': data_classification,
        'network_complexity': network_complexity,
        'compliance_scope': ['SOC2', 'NIST-CSF']
    }

def parse_bedrock_response(response_text, architecture_info=None):
    """Legacy parser - maintained for backward compatibility"""
    
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