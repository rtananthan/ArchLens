#!/usr/bin/env python3
"""
Mock server for local development testing
This simulates the ArchLens API without requiring AWS services
"""

import json
import time
import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.xml_parser import DrawIOParser

app = FastAPI(title="ArchLens Mock API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for mock data
mock_analyses: Dict[str, Dict[str, Any]] = {}
xml_parser = DrawIOParser()

@app.get("/")
async def root():
    return {"message": "ArchLens Mock API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": str(uuid.uuid4()),
        "region": "local",
        "services": {
            "upload_bucket": True,
            "analysis_table": True,
            "bedrock_agent": False  # Mock doesn't have real Bedrock
        }
    }

@app.post("/api/analyze")
async def analyze_architecture(file: UploadFile = File(...)):
    """Upload and analyze draw.io file - Mock version"""
    try:
        # Validate file
        if not file.filename or not file.filename.endswith(('.xml', '.drawio')):
            raise HTTPException(
                status_code=400, 
                detail="Only .xml and .drawio files are supported"
            )
        
        # Read file content
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )
        
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Parse XML immediately to generate description
        description = None
        try:
            xml_content = file_content.decode('utf-8')
            architecture_data = xml_parser.parse(xml_content)
            description = xml_parser.generate_architecture_description(architecture_data)
            print(f"Generated description for {analysis_id}: {len(description)} characters")
        except Exception as e:
            print(f"Failed to generate immediate description: {e}")
            description = "Architecture uploaded successfully. This is a mock server for local testing."
        
        # Store mock analysis
        mock_analyses[analysis_id] = {
            "analysis_id": analysis_id,
            "status": "pending",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "file_name": file.filename,
            "file_size": len(file_content),
            "description": description,
            "created_at": time.time()
        }
        
        return {
            "analysis_id": analysis_id,
            "status": "pending",
            "message": "Analysis started successfully (mock mode)",
            "description": description
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Analysis request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/analysis/{analysis_id}/status")
async def get_analysis_status(analysis_id: str):
    """Get analysis status - Mock version"""
    if analysis_id not in mock_analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis = mock_analyses[analysis_id]
    
    # Simulate processing time
    elapsed = time.time() - analysis["created_at"]
    
    if elapsed < 5:  # First 5 seconds
        status = "pending"
        progress = 0.1
    elif elapsed < 15:  # Next 10 seconds
        status = "processing"
        progress = 0.3 + (elapsed - 5) / 10 * 0.6  # Progress from 30% to 90%
    else:  # After 15 seconds
        status = "completed"
        progress = 1.0
        # Update the stored analysis
        analysis["status"] = "completed"
    
    return {
        "analysis_id": analysis_id,
        "status": status,
        "timestamp": analysis["timestamp"],
        "progress": progress
    }

@app.get("/api/analysis/{analysis_id}")
async def get_analysis_results(analysis_id: str):
    """Get analysis results - Mock version"""
    if analysis_id not in mock_analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis = mock_analyses[analysis_id]
    
    # Simulate processing time
    elapsed = time.time() - analysis["created_at"]
    
    if elapsed < 15:
        # Still processing
        return {
            "analysis_id": analysis_id,
            "status": analysis["status"],
            "timestamp": analysis["timestamp"],
            "file_name": analysis["file_name"],
            "description": analysis["description"]
        }
    
    # Generate mock results based on what was actually detected
    if "No AWS services were detected" in analysis["description"]:
        # Handle empty/insufficient diagrams
        mock_results = {
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
                    },
                    {
                        "severity": "MEDIUM",
                        "component": "Documentation",
                        "issue": "Insufficient architectural detail for comprehensive analysis",
                        "recommendation": "Include specific AWS service names and connections between components",
                        "aws_service": "Documentation"
                    }
                ],
                "recommendations": [
                    "Include AWS service icons or clear service names in your diagram",
                    "Add connections between services to show data flow",
                    "Consider using AWS architecture icons for better recognition",
                    "Label components with specific AWS services (e.g., 'RDS MySQL', 'Lambda Function')",
                    "Review AWS Well-Architected Framework for architecture guidance"
                ]
            }
        }
    elif "Limited architecture detected" in analysis["description"] or analysis["description"].count("service") <= 2:
        # Handle minimal diagrams
        mock_results = {
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
                    },
                    {
                        "severity": "LOW",
                        "component": "Service Connectivity",
                        "issue": "Few or no connections shown between services",
                        "recommendation": "Add connections to show data flow and service relationships",
                        "aws_service": "General"
                    }
                ],
                "recommendations": [
                    "Add more AWS services to represent complete architecture",
                    "Include security services (IAM, VPC, Security Groups)",
                    "Show connections between services",
                    "Consider adding monitoring and logging services",
                    "Include data storage and networking components"
                ]
            }
        }
    else:
        # Full analysis for comprehensive diagrams
        mock_results = {
            "overall_score": 7.2,
            "security": {
                "score": 6.8,
                "issues": [
                    {
                        "severity": "HIGH",
                        "component": "S3 Bucket",
                        "issue": "Public read access enabled",
                        "recommendation": "Disable public access and use presigned URLs or CloudFront for content delivery",
                        "aws_service": "S3"
                    },
                    {
                        "severity": "MEDIUM",
                        "component": "VPC Configuration",
                        "issue": "No explicit security groups shown in diagram",
                        "recommendation": "Define security groups with least privilege access rules",
                        "aws_service": "VPC"
                    },
                    {
                        "severity": "LOW",
                        "component": "Database Connection",
                        "issue": "Database connection encryption not explicitly shown",
                        "recommendation": "Ensure RDS connections use SSL/TLS encryption in transit",
                        "aws_service": "RDS"
                    }
                ],
                "recommendations": [
                    "Enable AWS CloudTrail for comprehensive logging and monitoring",
                    "Implement AWS Config for compliance and configuration monitoring",
                    "Use AWS WAF to protect web applications from common exploits",
                    "Enable GuardDuty for threat detection and continuous monitoring",
                    "Implement least privilege IAM policies for all services"
                ]
            }
        }
    
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "timestamp": analysis["timestamp"],
        "file_name": analysis["file_name"],
        "description": analysis["description"],
        "results": mock_results
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting ArchLens Mock Server...")
    print("📱 Frontend should use: http://localhost:8000")
    print("🔗 API docs available at: http://localhost:8000/docs")
    print("🧪 This is a mock server for local testing only")
    uvicorn.run(app, host="0.0.0.0", port=8000)