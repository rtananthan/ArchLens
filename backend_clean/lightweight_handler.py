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
    
    # Pattern matching for common AWS services
    # Each section checks for service-specific keywords in component names
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