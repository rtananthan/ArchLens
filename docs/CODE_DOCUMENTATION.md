# ArchLens Code Documentation

## 📖 Overview

All ArchLens code has been enhanced with comprehensive comments to make it self-documenting for new developers. This documentation explains the commenting approach and highlights key areas for understanding the codebase.

## 🎯 Documentation Philosophy

### Code Comment Standards
- **Purpose-driven**: Comments explain WHY, not just what
- **Beginner-friendly**: Assumes reader is new to the codebase
- **Architecture-aware**: Links code to overall system design
- **Step-by-step**: Complex functions broken into numbered steps
- **Error-context**: Explains error handling strategies

### Comment Types Used

#### 1. File-level Headers
```python
# ArchLens Backend - Lightweight Lambda Handler
# This file contains the main API handler for processing architecture diagram uploads
# and coordinating with Amazon Bedrock for AI-powered security analysis.
```

#### 2. Function Documentation
```python
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
    """
```

#### 3. Step-by-step Process Comments
```python
# Step 1: Extract and decode the request body
# API Gateway can send data either as plain text or base64-encoded
body = event.get('body', '')
if event.get('isBase64Encoded', False):
    # Binary data (like file uploads) comes base64-encoded
    body = base64.b64decode(body)
```

#### 4. Technical Context Comments
```typescript
// CORS (Cross-Origin Resource Sharing) headers for browser compatibility
// These headers allow the frontend (running on CloudFront) to call this API
cors_headers = {
    'Content-Type': 'application/json',                               // Always return JSON
    'Access-Control-Allow-Origin': '*',                             // Allow all origins (can be restricted to CloudFront domain)
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',           // Supported HTTP methods
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'   // Headers the browser can send
}
```

## 🗂️ Documented Files

### Backend (`backend_clean/`)

#### `lightweight_handler.py` - Main API Handler
**Key Documentation Areas:**
- **Main handler function**: Request routing and response formatting
- **File upload processing**: Multipart form data parsing and S3 storage
- **XML parsing**: Draw.io component extraction and AWS service identification
- **Bedrock integration**: AI analysis with retry logic and error handling
- **Error handling**: Comprehensive error scenarios and user feedback

**Notable Comments:**
```python
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
```

### Frontend (`frontend/`)

#### `lib/api.ts` - API Client
**Key Documentation Areas:**
- **Axios configuration**: Timeout, interceptors, and base URL setup
- **API methods**: File upload, status checking, and result retrieval
- **Error handling**: Centralized error logging and propagation
- **TypeScript types**: Interface documentation for API responses

**Notable Comments:**
```typescript
/**
 * Upload and analyze architecture file
 * 
 * Takes a draw.io file from the user, uploads it to the backend,
 * and triggers the AI analysis workflow. This is the main entry point
 * for the application's core functionality.
 * 
 * @param file - The draw.io file selected by the user
 * @returns Promise with analysis ID and initial status
 */
async analyzeFile(file: File): Promise<AnalysisResponse>
```

#### `app/page.tsx` - Main Application Component
**Key Documentation Areas:**
- **State machine**: Application workflow phases and transitions
- **Event handlers**: File upload, analysis completion, and error handling
- **UI phases**: Upload, description, analyzing, results, and error states
- **Component integration**: How different React components work together

**Notable Comments:**
```typescript
// Application state machine - defines the different screens/phases of the app
// This creates a clear workflow that users follow from start to finish
type AppState = 'upload' | 'description' | 'analyzing' | 'results' | 'error'

/**
 * Handle file upload and initiate analysis workflow
 * 
 * This is the main entry point for user interaction. When a user selects
 * a file, this function:
 * 1. Updates UI to show loading state
 * 2. Sends file to backend for processing
 * 3. Handles the response and moves to next phase
 * 4. Manages error states and user feedback
 */
```

### Infrastructure (`infrastructure/stacks/`)

#### `compute_stack.py` - Serverless Compute Infrastructure
**Key Documentation Areas:**
- **CDK imports**: AWS service modules and their purposes
- **IAM permissions**: Least-privilege access patterns
- **Lambda configuration**: Memory, timeout, and environment settings
- **API Gateway setup**: CORS, routing, and integration patterns

**Notable Comments:**
```python
# Step 1: Create IAM role for Lambda functions
# This role defines what AWS services the Lambda functions can access
lambda_role = iam.Role(
    self, 'LambdaExecutionRole',
    assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),  # Allow Lambda service to assume this role
    managed_policies=[
        # AWS-managed policy for basic Lambda logging to CloudWatch
        iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
    ],
```

## 🧭 Navigation Guide for New Developers

### Understanding the Data Flow
1. **Start with `frontend/app/page.tsx`** - See the user workflow
2. **Follow to `frontend/lib/api.ts`** - Understand API communication
3. **Move to `backend_clean/lightweight_handler.py`** - See backend processing
4. **Review `infrastructure/stacks/`** - Understand AWS deployment

### Key Functions to Understand

#### Backend Entry Points
```python
def handler(event, context):                    # Main Lambda entry point
def handle_file_upload():                       # File processing workflow
def parse_uploaded_xml():                       # Architecture component extraction
def call_bedrock_agent():                       # AI analysis integration
```

#### Frontend Entry Points
```typescript
const handleFileSelect = async (file: File)    # User file selection
const analysisApi.analyzeFile()                # Backend communication
const AnalysisProgress                          # Real-time progress tracking
const AnalysisResults                           # Results display
```

#### Infrastructure Entry Points
```python
class ComputeStack:                             # Lambda and API Gateway
class StorageStack:                             # S3 and DynamoDB
class AIStack:                                  # Bedrock agent configuration
```

## 🔍 Understanding Complex Logic

### File Upload Processing
The file upload process involves several complex steps that are well-documented:

1. **Multipart parsing** - Extracting files from browser form data
2. **XML extraction** - Finding draw.io content within multipart boundaries
3. **Component identification** - Mapping diagram elements to AWS services
4. **AI analysis** - Structured prompts and response parsing

### Error Handling Patterns
The codebase uses consistent error handling patterns:

1. **Try-catch with context** - Each error handler explains the scenario
2. **User-friendly messages** - Technical errors converted to actionable feedback
3. **Fallback responses** - Graceful degradation when AI services are unavailable
4. **Logging for debugging** - Detailed error logging for troubleshooting

### State Management
Frontend state management is documented to show:

1. **State machine approach** - Clear phases and transitions
2. **Loading states** - How UI responds to async operations
3. **Error recovery** - How users can recover from failures
4. **Data flow** - How information moves between components

## 📚 Additional Resources

### Understanding AWS Services
Comments link to AWS service concepts:
- **Lambda**: Serverless compute explanations
- **API Gateway**: REST API and CORS concepts
- **S3**: Object storage and lifecycle management
- **DynamoDB**: NoSQL database and TTL concepts
- **Bedrock**: AI/ML service integration patterns

### Understanding Frontend Patterns
Comments explain React patterns:
- **Hooks**: useState and useEffect usage patterns
- **Components**: Composition and prop passing
- **API integration**: Async data fetching and error handling
- **State machines**: Application workflow management

### Understanding Infrastructure Patterns
Comments explain CDK patterns:
- **Stack dependencies**: How stacks reference each other
- **Resource configuration**: AWS service setup patterns
- **IAM security**: Least-privilege access principles
- **Tagging strategies**: Cost allocation and resource management

## 🎓 Learning Path for New Developers

### Beginner (First Week)
1. Read file headers to understand each module's purpose
2. Follow the main user workflow in `app/page.tsx`
3. Understand the API structure in `lib/api.ts`
4. Review the basic Lambda handler structure

### Intermediate (Second Week)
1. Dive into file processing logic in `lightweight_handler.py`
2. Understand XML parsing and AWS service identification
3. Study the Bedrock integration and retry logic
4. Review infrastructure setup in CDK stacks

### Advanced (Third Week)
1. Understand error handling strategies across the stack
2. Study the IAM permission model and security patterns
3. Learn the deployment pipeline and environment management
4. Explore optimization opportunities and scaling considerations

---

**💡 Pro Tip**: The comments are designed to be read in sequence - each function's comments build on previous explanations, creating a guided tour through the codebase.