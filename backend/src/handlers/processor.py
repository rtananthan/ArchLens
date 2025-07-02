import os
import json
import logging
import asyncio
from typing import Dict, Any
from ..models.analysis import AnalysisStatus, AnalysisResults, SecurityAnalysis, SecurityIssue, IssueSeverity
from ..services.storage_service import StorageService
from ..services.bedrock_service import BedrockService
from ..utils.xml_parser import DrawIOParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
UPLOAD_BUCKET = os.getenv('UPLOAD_BUCKET')
ANALYSIS_TABLE = os.getenv('ANALYSIS_TABLE')
BEDROCK_AGENT_ID = os.getenv('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.getenv('BEDROCK_AGENT_ALIAS_ID')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize services
storage_service = StorageService(AWS_REGION)
bedrock_service = BedrockService(AWS_REGION)
xml_parser = DrawIOParser()

async def process_analysis(analysis_id: str, s3_key: str, bucket: str) -> Dict[str, Any]:
    """Process the architecture analysis"""
    try:
        # Update status to processing
        storage_service.update_analysis_status(
            ANALYSIS_TABLE, 
            analysis_id, 
            AnalysisStatus.PROCESSING
        )
        
        logger.info(f"Starting analysis for {analysis_id}")
        
        # Download file from S3
        file_content = storage_service.get_file_from_s3(bucket, s3_key)
        
        # Parse XML
        xml_content = file_content.decode('utf-8')
        architecture_data = xml_parser.parse(xml_content)
        
        logger.info(f"Parsed architecture data: {len(architecture_data.get('services', []))} services found")
        
        # Perform AI analysis
        if BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID:
            ai_results = await bedrock_service.analyze_architecture(
                architecture_data, 
                BEDROCK_AGENT_ID, 
                BEDROCK_AGENT_ALIAS_ID
            )
        else:
            # Fallback to basic analysis
            logger.warning("Bedrock agent not configured, using fallback analysis")
            ai_results = create_fallback_analysis(architecture_data)
        
        # Process and structure results
        analysis_results = process_ai_results(ai_results, architecture_data)
        
        # Update record with results
        storage_service.update_analysis_status(
            ANALYSIS_TABLE,
            analysis_id,
            AnalysisStatus.COMPLETED,
            results=analysis_results.model_dump()
        )
        
        logger.info(f"Analysis completed for {analysis_id}")
        
        # Clean up uploaded file (optional, or keep for audit)
        # storage_service.delete_file_from_s3(bucket, s3_key)
        
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Analysis completed successfully"})
        }
        
    except Exception as e:
        logger.error(f"Analysis processing failed for {analysis_id}: {e}")
        
        # Update record with error
        storage_service.update_analysis_status(
            ANALYSIS_TABLE,
            analysis_id,
            AnalysisStatus.FAILED,
            error_message=str(e)
        )
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

def create_fallback_analysis(architecture_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a fallback analysis when Bedrock is not available"""
    services = architecture_data.get('services', [])
    security_analysis = architecture_data.get('security_analysis', {})
    
    # Handle insufficient detail scenarios
    if not services:
        return {
            "analysis_id": "fallback-analysis",
            "status": "completed",
            "results": {
                "overall_score": 1.0,
                "security": {
                    "score": 1.0,
                    "issues": [
                        {
                            "severity": "HIGH",
                            "component": "Architecture",
                            "issue": "No AWS services detected in diagram",
                            "recommendation": "Add AWS services with proper labels (e.g., 'EC2 Instance', 'S3 Bucket', 'RDS Database')",
                            "aws_service": "General"
                        }
                    ],
                    "recommendations": [
                        "Include AWS service icons or clear service names in your diagram",
                        "Add connections between services to show data flow",
                        "Consider using AWS architecture icons for better recognition",
                        "Review AWS Well-Architected Framework for architecture guidance"
                    ]
                }
            }
        }
    
    if len(services) <= 2:
        return {
            "analysis_id": "fallback-analysis", 
            "status": "completed",
            "results": {
                "overall_score": 3.0,
                "security": {
                    "score": 3.0,
                    "issues": [
                        {
                            "severity": "MEDIUM",
                            "component": "Architecture Completeness",
                            "issue": "Limited services detected - may not represent complete architecture",
                            "recommendation": "Consider adding security services like IAM, VPC, CloudWatch for comprehensive analysis",
                            "aws_service": "Architecture"
                        }
                    ],
                    "recommendations": [
                        "Add more AWS services to represent complete architecture",
                        "Include security services (IAM, VPC, Security Groups)",
                        "Show connections between services",
                        "Consider adding monitoring and logging services"
                    ]
                }
            }
        }
    
    # Basic scoring based on service types and configuration
    security_score = calculate_basic_security_score(services, security_analysis)
    overall_score = security_score  # For now, only security analysis
    
    # Generate basic security issues
    issues = generate_basic_security_issues(services, security_analysis)
    
    return {
        "analysis_id": "fallback-analysis",
        "status": "completed",
        "results": {
            "overall_score": overall_score,
            "security": {
                "score": security_score,
                "issues": issues,
                "recommendations": [
                    "Review all public-facing services for proper security configuration",
                    "Ensure all data stores are encrypted at rest and in transit",
                    "Implement least privilege access controls with IAM",
                    "Enable AWS CloudTrail and CloudWatch for monitoring",
                    "Consider implementing AWS WAF for web applications"
                ]
            }
        }
    }

def calculate_basic_security_score(services: list, security_analysis: Dict[str, Any]) -> float:
    """Calculate basic security score"""
    if not services:
        return 5.0  # Neutral score for empty diagrams
    
    score = 8.0  # Start with good score
    
    # Deduct points for security issues
    public_services = len(security_analysis.get('public_services', []))
    unencrypted_services = len(security_analysis.get('unencrypted_services', []))
    security_service_count = security_analysis.get('security_service_count', 0)
    
    # Penalty for public services without proper justification
    if public_services > 0:
        score -= min(2.0, public_services * 0.5)
    
    # Penalty for potentially unencrypted services
    if unencrypted_services > 0:
        score -= min(1.5, unencrypted_services * 0.3)
    
    # Bonus for security services
    if security_service_count > 0:
        score += min(1.0, security_service_count * 0.2)
    
    return max(0.0, min(10.0, score))

def generate_basic_security_issues(services: list, security_analysis: Dict[str, Any]) -> list:
    """Generate basic security issues"""
    issues = []
    
    # Check for public services
    for service in security_analysis.get('public_services', []):
        issues.append({
            "severity": "HIGH",
            "component": service.get('label', 'Unknown Service'),
            "issue": "Service appears to be publicly accessible",
            "recommendation": "Review public access requirements and implement appropriate security controls",
            "aws_service": service.get('type', 'Unknown').upper()
        })
    
    # Check for potentially unencrypted services
    for service in security_analysis.get('unencrypted_services', []):
        issues.append({
            "severity": "MEDIUM",
            "component": service.get('label', 'Unknown Service'),
            "issue": "Service may not have encryption configured",
            "recommendation": "Enable encryption at rest and in transit for all data stores",
            "aws_service": service.get('type', 'Unknown').upper()
        })
    
    # Check for missing security services
    service_types = {s.get('type') for s in services}
    if 'iam' not in service_types:
        issues.append({
            "severity": "MEDIUM",
            "component": "Architecture",
            "issue": "No IAM service explicitly shown in diagram",
            "recommendation": "Ensure proper IAM roles and policies are configured for all services",
            "aws_service": "IAM"
        })
    
    if 'waf' not in service_types and any(s.get('type') in ['apigateway', 'elb'] for s in services):
        issues.append({
            "severity": "LOW",
            "component": "Web Services",
            "issue": "Web services without WAF protection",
            "recommendation": "Consider implementing AWS WAF for web application protection",
            "aws_service": "WAF"
        })
    
    return issues

def process_ai_results(ai_results: Dict[str, Any], architecture_data: Dict[str, Any]) -> AnalysisResults:
    """Process AI results into structured analysis results"""
    try:
        results_data = ai_results.get('results', {})
        security_data = results_data.get('security', {})
        
        # Process security issues
        security_issues = []
        for issue_data in security_data.get('issues', []):
            try:
                issue = SecurityIssue(
                    severity=IssueSeverity(issue_data.get('severity', 'MEDIUM')),
                    component=issue_data.get('component', 'Unknown'),
                    issue=issue_data.get('issue', 'No description available'),
                    recommendation=issue_data.get('recommendation', 'No recommendation available'),
                    aws_service=issue_data.get('aws_service')
                )
                security_issues.append(issue)
            except Exception as e:
                logger.warning(f"Failed to process security issue: {e}")
        
        # Create security analysis
        security_analysis = SecurityAnalysis(
            score=float(security_data.get('score', 5.0)),
            issues=security_issues,
            recommendations=security_data.get('recommendations', [])
        )
        
        # Create overall results
        return AnalysisResults(
            overall_score=float(results_data.get('overall_score', 5.0)),
            security=security_analysis
        )
        
    except Exception as e:
        logger.error(f"Failed to process AI results: {e}")
        # Return fallback results
        return AnalysisResults(
            overall_score=5.0,
            security=SecurityAnalysis(
                score=5.0,
                issues=[
                    SecurityIssue(
                        severity=IssueSeverity.MEDIUM,
                        component="Analysis System",
                        issue="Failed to process detailed analysis results",
                        recommendation="Manual review recommended"
                    )
                ],
                recommendations=["Manual architecture review recommended"]
            )
        )

def handler(event, context):
    """Lambda handler for processor function"""
    try:
        # Extract parameters from event
        analysis_id = event.get('analysis_id')
        s3_key = event.get('s3_key')
        bucket = event.get('bucket')
        
        if not all([analysis_id, s3_key, bucket]):
            raise ValueError("Missing required parameters: analysis_id, s3_key, bucket")
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                process_analysis(analysis_id, s3_key, bucket)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Processor handler failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }