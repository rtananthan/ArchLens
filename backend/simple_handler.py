import json
import boto3
import os
from uuid import uuid4
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Simple Lambda handler for testing basic functionality
    """
    print(f"Event: {json.dumps(event)}")
    
    # Get the HTTP method and path
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    # Simple routing
    if path == '/api/health' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'status': 'healthy',
                'message': 'ArchLens API is running',
                'version': '1.0.0',
                'environment_variables': {
                    'UPLOAD_BUCKET': os.environ.get('UPLOAD_BUCKET', 'not-set'),
                    'ANALYSIS_TABLE': os.environ.get('ANALYSIS_TABLE', 'not-set'),
                    'BEDROCK_AGENT_ID': os.environ.get('BEDROCK_AGENT_ID', 'not-set')
                }
            })
        }
    
    # File upload endpoint
    elif path == '/api/analyze' and http_method == 'POST':
        # Mock file analysis response
        analysis_id = f"analysis_{uuid4().hex[:8]}"
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'analysis_id': analysis_id,
                'status': 'completed',
                'message': 'File uploaded and analyzed successfully (mock)',
                'description': 'This is a mock response. The file upload was received but not processed by real AI yet.',
                'timestamp': '2025-07-02T12:30:00Z'
            })
        }
    
    # Get analysis results
    elif path.startswith('/api/analysis/') and http_method == 'GET':
        # Extract analysis_id from path like /api/analysis/analysis_12345
        path_parts = path.split('/')
        if len(path_parts) >= 4:
            analysis_id = path_parts[3]
            
            # Check if this is a status request
            if len(path_parts) >= 5 and path_parts[4] == 'status':
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps({
                        'analysis_id': analysis_id,
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Analysis completed successfully (mock)'
                    })
                }
            else:
                # Return full analysis results
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps({
                        'analysis_id': analysis_id,
                        'status': 'completed',
                        'description': 'Mock AWS architecture analysis: This diagram shows a basic web application with security considerations for improvement.',
                        'overall_score': 7.2,
                        'security': {
                            'score': 7.2,
                            'issues': [
                                {
                                    'severity': 'MEDIUM',
                                    'component': 'Application Load Balancer',
                                    'issue': 'ALB should use HTTPS listener with SSL certificate',
                                    'recommendation': 'Configure SSL/TLS certificate and redirect HTTP to HTTPS',
                                    'aws_service': 'ALB'
                                },
                                {
                                    'severity': 'LOW',
                                    'component': 'EC2 Instance',
                                    'issue': 'Consider using Systems Manager Session Manager instead of SSH',
                                    'recommendation': 'Enable SSM Session Manager for secure instance access',
                                    'aws_service': 'EC2'
                                }
                            ],
                            'recommendations': [
                                'Implement Web Application Firewall (WAF) for additional protection',
                                'Enable VPC Flow Logs for network monitoring',
                                'Use AWS Certificate Manager for SSL certificates'
                            ]
                        },
                        'timestamp': '2025-07-02T12:30:00Z'
                    })
                }
    
    # Handle CORS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': ''
        }
    
    # Default response
    return {
        'statusCode': 404,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': 'Not Found',
            'message': f'Path {path} not found',
            'path': path,
            'method': http_method
        })
    }