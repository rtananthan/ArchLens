# 🔧 Quick Debug Guide

## The Issue
You're getting "something went wrong" when uploading files.

## Let's Debug Step by Step

### 1. Check Both Servers Are Running
```bash
# Check backend (should return JSON)
curl http://localhost:8000/api/health

# Check frontend (should return HTML)
curl -I http://localhost:3000
```

### 2. Test API Directly
```bash
# Test file upload directly to backend
curl -X POST -F "file=@examples/sample-aws-architecture.xml" http://localhost:8000/api/analyze
```

### 3. Check Browser Console
1. Open http://localhost:3000
2. Open browser Developer Tools (F12)
3. Go to Console tab
4. Look for messages starting with "API_BASE_URL:" and "Environment:"
5. Try uploading a file and watch for error messages

### 4. Common Issues & Fixes

**Issue**: Environment variable not loaded
**Solution**: Check that `.env.local` exists in frontend folder with:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Issue**: CORS error in browser console
**Solution**: Backend CORS is configured for all origins, should work

**Issue**: Network error
**Solution**: Make sure backend is running on port 8000

### 5. Manual Test
Open this file in browser: `file:///Users/ananthan/Projects/ArchLens/debug_api.html`
- Click "Test Health" - should show JSON response
- Click "Test Upload" - should show analysis response

### 6. If Still Broken
The most likely issue is that the frontend environment variable isn't being read properly.

Try manually setting the API URL in the code:
1. Edit `frontend/lib/api.ts`
2. Change line 4 to: `const API_BASE_URL = 'http://localhost:8000'`
3. Restart frontend

This will bypass the environment variable and connect directly to the backend.

## Expected Results

**Health Check Response:**
```json
{
  "status": "healthy",
  "timestamp": "uuid",
  "region": "local",
  "services": {
    "upload_bucket": true,
    "analysis_table": true,
    "bedrock_agent": false
  }
}
```

**Upload Response:**
```json
{
  "analysis_id": "uuid",
  "status": "pending",
  "message": "Analysis started successfully (mock mode)",
  "description": "**AWS Security Architecture**\n\nThis architecture diagram contains **9 AWS services**..."
}
```

If you see these responses, the API is working and the issue is in the frontend connection.