# ArchLens API Documentation

This document describes the REST API endpoints for the ArchLens AWS Architecture Analysis service.

## Base URL

```
https://your-api-gateway-url/api
```

## Authentication

Currently, no authentication is required for the MVP version. All endpoints are publicly accessible.

## Endpoints

### Health Check

Check the health status of the API service.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "uuid-timestamp",
  "region": "us-east-1",
  "services": {
    "upload_bucket": true,
    "analysis_table": true,
    "bedrock_agent": true
  }
}
```

**Response Codes:**
- `200 OK`: Service is healthy
- `500 Internal Server Error`: Service has issues

---

### Analyze Architecture

Upload and analyze a draw.io architecture file.

**Endpoint:** `POST /analyze`

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:** File upload with key `file`

**File Requirements:**
- **Format:** `.xml` or `.drawio` files
- **Size:** Maximum 10MB
- **Content:** Valid draw.io XML format

**Response:**
```json
{
  "analysis_id": "uuid-string",
  "status": "pending", 
  "message": "Analysis started successfully",
  "description": "**AWS Security Architecture**\n\nThis architecture diagram contains **8 AWS services** with **6 connections** between components.\n\nThe architecture includes: 1 Internet Gateway, 1 VPC network, 1 Load Balancer, 1 EC2 instance, 1 RDS database, 1 S3 bucket, 1 Lambda function, and 1 API Gateway.\n\n**Architecture Patterns Detected:** Load-balanced web application, Serverless API\n\n**Data Flow:** Traffic enters through Internet Gateway and flows to RDS database.\n\n**Security Aspects:** Includes VPC network isolation."
}
```

**Response Codes:**
- `200 OK`: Analysis started successfully
- `400 Bad Request`: Invalid file format or size
- `500 Internal Server Error`: Analysis initialization failed

**Example:**
```bash
curl -X POST \
  https://your-api-url/api/analyze \
  -F "file=@architecture.xml"
```

---

### Get Analysis Status

Check the current status of an analysis.

**Endpoint:** `GET /analysis/{analysis_id}/status`

**Parameters:**
- `analysis_id` (path): The UUID of the analysis

**Response:**
```json
{
  "analysis_id": "uuid-string",
  "status": "processing",
  "timestamp": "2024-01-01T10:00:00Z",
  "progress": 0.5,
  "estimated_completion": "2024-01-01T10:05:00Z"
}
```

**Status Values:**
- `pending`: Analysis is queued
- `processing`: Analysis is in progress
- `completed`: Analysis finished successfully
- `failed`: Analysis encountered an error

**Response Codes:**
- `200 OK`: Status retrieved successfully
- `404 Not Found`: Analysis ID not found
- `500 Internal Server Error`: Status check failed

**Example:**
```bash
curl https://your-api-url/api/analysis/123e4567-e89b-12d3-a456-426614174000/status
```

---

### Get Analysis Results

Retrieve the complete analysis results.

**Endpoint:** `GET /analysis/{analysis_id}`

**Parameters:**
- `analysis_id` (path): The UUID of the analysis

**Response:**
```json
{
  "analysis_id": "uuid-string",
  "status": "completed",
  "timestamp": "2024-01-01T10:00:00Z",
  "file_name": "architecture.xml",
  "description": "**AWS Security Architecture**\n\nThis architecture diagram contains **8 AWS services** with **6 connections** between components...",
  "results": {
    "overall_score": 7.5,
    "security": {
      "score": 6.8,
      "issues": [
        {
          "severity": "HIGH",
          "component": "S3 Bucket",
          "issue": "Public read access enabled",
          "recommendation": "Disable public access and use presigned URLs",
          "aws_service": "S3"
        }
      ],
      "recommendations": [
        "Enable encryption at rest for all data stores",
        "Implement least privilege access controls"
      ]
    }
  }
}
```

**Response Codes:**
- `200 OK`: Results retrieved successfully
- `404 Not Found`: Analysis ID not found
- `500 Internal Server Error`: Results retrieval failed

**Example:**
```bash
curl https://your-api-url/api/analysis/123e4567-e89b-12d3-a456-426614174000
```

## Data Models

### Analysis Status

```typescript
type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'
```

### Issue Severity

```typescript
type IssueSeverity = 'HIGH' | 'MEDIUM' | 'LOW'
```

### Security Issue

```typescript
interface SecurityIssue {
  severity: IssueSeverity
  component: string
  issue: string
  recommendation: string
  aws_service?: string
}
```

### Security Analysis

```typescript
interface SecurityAnalysis {
  score: number // 0-10
  issues: SecurityIssue[]
  recommendations: string[]
}
```

### Analysis Results

```typescript
interface AnalysisResults {
  overall_score: number // 0-10
  security: SecurityAnalysis
  performance?: any // Future feature
  cost?: any // Future feature
  reliability?: any // Future feature
  operational_excellence?: any // Future feature
}
```

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

### Common Error Codes

#### 400 Bad Request
- Invalid file format
- File size exceeds limit
- Missing required parameters

#### 404 Not Found
- Analysis ID does not exist
- Resource not found

#### 429 Too Many Requests
- Rate limit exceeded
- API throttling active

#### 500 Internal Server Error
- AWS service unavailable
- Bedrock analysis failed
- Database connection error

## Rate Limiting

Current rate limits:
- **API Gateway**: 100 requests/second burst, 200 requests/second steady
- **File uploads**: 10MB maximum size
- **Analysis**: No concurrent limit per user (no auth)

## Example Workflows

### Complete Analysis Workflow

```javascript
// 1. Upload and start analysis
const formData = new FormData()
formData.append('file', fileInput.files[0])

const startResponse = await fetch('/api/analyze', {
  method: 'POST',
  body: formData
})
const { analysis_id } = await startResponse.json()

// 2. Poll for status
const pollStatus = async () => {
  const statusResponse = await fetch(`/api/analysis/${analysis_id}/status`)
  const status = await statusResponse.json()
  
  if (status.status === 'completed') {
    // 3. Get results
    const resultsResponse = await fetch(`/api/analysis/${analysis_id}`)
    const results = await resultsResponse.json()
    return results
  } else if (status.status === 'failed') {
    throw new Error('Analysis failed')
  } else {
    // Continue polling
    setTimeout(pollStatus, 2000)
  }
}

await pollStatus()
```

### Error Handling Example

```javascript
try {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    body: formData
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail)
  }
  
  const result = await response.json()
  // Handle success
} catch (error) {
  console.error('Analysis failed:', error.message)
  // Handle error appropriately
}
```

## Testing

### Health Check Test

```bash
curl -s https://your-api-url/api/health | jq .
```

### Upload Test with Sample File

```bash
curl -X POST \
  -F "file=@examples/sample-aws-architecture.xml" \
  https://your-api-url/api/analyze
```

### Complete Integration Test

```bash
#!/bin/bash
API_URL="https://your-api-url/api"

# 1. Health check
echo "Testing health endpoint..."
curl -s $API_URL/health

# 2. Upload file
echo "Uploading test file..."
RESPONSE=$(curl -s -X POST -F "file=@examples/sample-aws-architecture.xml" $API_URL/analyze)
ANALYSIS_ID=$(echo $RESPONSE | jq -r .analysis_id)

echo "Analysis ID: $ANALYSIS_ID"

# 3. Poll status
echo "Polling status..."
while true; do
  STATUS=$(curl -s $API_URL/analysis/$ANALYSIS_ID/status | jq -r .status)
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 2
done

# 4. Get results
echo "Getting results..."
curl -s $API_URL/analysis/$ANALYSIS_ID | jq .
```

## Monitoring and Logging

### CloudWatch Metrics

The API automatically logs the following metrics:
- Request count per endpoint
- Response times
- Error rates
- File upload sizes

### Custom Logging

Each request generates structured logs:
```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "level": "INFO",
  "request_id": "uuid",
  "endpoint": "/api/analyze",
  "method": "POST",
  "file_size": 1024576,
  "analysis_id": "uuid",
  "duration_ms": 1500
}
```

### Health Monitoring

Monitor these endpoints for service health:
- `/api/health` - Overall service health
- CloudWatch Lambda metrics
- DynamoDB table metrics
- S3 bucket metrics