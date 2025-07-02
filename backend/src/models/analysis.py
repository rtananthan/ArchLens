from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

class IssueSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class SecurityIssue(BaseModel):
    severity: IssueSeverity
    component: str
    issue: str
    recommendation: str
    aws_service: Optional[str] = None

class SecurityAnalysis(BaseModel):
    score: float = Field(..., ge=0.0, le=10.0)
    issues: List[SecurityIssue] = []
    recommendations: List[str] = []

class AnalysisResults(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=10.0)
    security: SecurityAnalysis
    performance: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    reliability: Optional[Dict[str, Any]] = None
    operational_excellence: Optional[Dict[str, Any]] = None

class AnalysisRecord(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    timestamp: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    description: Optional[str] = None  # Immediate architecture description
    results: Optional[AnalysisResults] = None
    error_message: Optional[str] = None
    ttl: Optional[int] = None  # TTL for DynamoDB
    
    @classmethod
    def create_new(cls, analysis_id: str, file_name: str, file_size: int) -> 'AnalysisRecord':
        """Create a new analysis record"""
        now = datetime.utcnow()
        ttl = int(now.timestamp()) + (48 * 60 * 60)  # 48 hours from now
        
        return cls(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
            timestamp=now.isoformat() + 'Z',
            file_name=file_name,
            file_size=file_size,
            ttl=ttl
        )

class AnalysisRequest(BaseModel):
    file_name: str
    file_size: int

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    message: str
    description: Optional[str] = None  # Immediate architecture description

class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    timestamp: str
    progress: Optional[float] = None
    estimated_completion: Optional[str] = None

class AnalysisDetailResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    timestamp: str
    file_name: Optional[str] = None
    description: Optional[str] = None  # Immediate architecture description
    results: Optional[AnalysisResults] = None
    error_message: Optional[str] = None