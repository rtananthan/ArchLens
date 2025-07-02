import os
import json
import logging
import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from ..models.analysis import (
    AnalysisRecord, AnalysisStatus, AnalysisResponse, 
    AnalysisStatusResponse, AnalysisDetailResponse
)
from ..services.storage_service import StorageService
from ..services.bedrock_service import BedrockService
from ..utils.xml_parser import DrawIOParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ArchLens API",
    description="AWS Architecture Analysis API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "ArchLens API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": str(uuid.uuid4()),
        "region": AWS_REGION,
        "services": {
            "upload_bucket": bool(UPLOAD_BUCKET),
            "analysis_table": bool(ANALYSIS_TABLE),
            "bedrock_agent": bool(BEDROCK_AGENT_ID)
        }
    }

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_architecture(file: UploadFile = File(...)):
    """Upload and analyze draw.io file"""
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
            logger.info(f"Generated description for {analysis_id}: {len(description)} characters")
        except Exception as e:
            logger.warning(f"Failed to generate immediate description: {e}")
            description = "Architecture uploaded successfully. Detailed analysis in progress..."
        
        # Upload file to S3
        s3_key = f"uploads/{analysis_id}/{file.filename}"
        storage_service.upload_file_to_s3(
            UPLOAD_BUCKET, 
            s3_key, 
            file_content,
            'application/xml'
        )
        
        # Create analysis record with description
        record = AnalysisRecord.create_new(
            analysis_id=analysis_id,
            file_name=file.filename,
            file_size=len(file_content)
        )
        record.description = description
        
        # Save initial record
        storage_service.save_analysis_record(ANALYSIS_TABLE, record)
        
        # Start async processing (invoke processor Lambda)
        await invoke_processor_lambda(analysis_id, s3_key)
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
            message="Analysis started successfully",
            description=description
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/analysis/{analysis_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(analysis_id: str):
    """Get analysis status"""
    try:
        record = storage_service.get_analysis_record(ANALYSIS_TABLE, analysis_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Calculate progress estimate
        progress = None
        if record.status == AnalysisStatus.PROCESSING:
            progress = 0.5  # Rough estimate
        elif record.status == AnalysisStatus.COMPLETED:
            progress = 1.0
        
        return AnalysisStatusResponse(
            analysis_id=analysis_id,
            status=record.status,
            timestamp=record.timestamp,
            progress=progress
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/api/analysis/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis_results(analysis_id: str):
    """Get analysis results"""
    try:
        record = storage_service.get_analysis_record(ANALYSIS_TABLE, analysis_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return AnalysisDetailResponse(
            analysis_id=analysis_id,
            status=record.status,
            timestamp=record.timestamp,
            file_name=record.file_name,
            description=record.description,
            results=record.results,
            error_message=record.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Results fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Results fetch failed: {str(e)}")

async def invoke_processor_lambda(analysis_id: str, s3_key: str):
    """Invoke the processor Lambda function asynchronously"""
    try:
        import boto3
        
        lambda_client = boto3.client('lambda', region_name=AWS_REGION)
        
        # Get processor function name from environment or construct it
        processor_function_name = os.getenv('PROCESSOR_FUNCTION_NAME', 
                                          f"ArchLens-Compute-ProcessorLambda")
        
        payload = {
            "analysis_id": analysis_id,
            "s3_key": s3_key,
            "bucket": UPLOAD_BUCKET
        }
        
        lambda_client.invoke(
            FunctionName=processor_function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Processor Lambda invoked for analysis {analysis_id}")
        
    except Exception as e:
        logger.error(f"Failed to invoke processor Lambda: {e}")
        # Update record with error
        storage_service.update_analysis_status(
            ANALYSIS_TABLE, 
            analysis_id, 
            AnalysisStatus.FAILED,
            error_message=f"Failed to start processing: {str(e)}"
        )

# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Lambda handler
handler = Mangum(app, lifespan="off")