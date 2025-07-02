# 🚀 Start ArchLens Locally

## ✅ Current Status
Both servers are now running:
- **Backend**: http://localhost:8000 ✅
- **Frontend**: http://localhost:3000 ✅

## 🌐 Access the Application

**Open your browser and go to: http://localhost:3000**

## 🧪 Test the New Architecture Description Feature

### 1. Upload Test File
- Go to http://localhost:3000
- Upload the sample file: `examples/sample-aws-architecture.xml`
- Drag and drop or click to select

### 2. See Instant Description
You should immediately see:
- Architecture description with service breakdown
- Pattern detection (e.g., "Load-balanced web application")
- Data flow analysis
- Security aspects

### 3. Continue to Mock Analysis
- Click "Continue to Security Analysis" 
- Watch 15-second mock analysis
- See full security results

## 📋 Manual Startup (if needed)

If servers stop, restart them manually:

### Backend:
```bash
cd backend
source venv/bin/activate
python mock_server.py
```

### Frontend (in new terminal):
```bash
cd frontend  
npm run dev
```

## 🔧 Useful URLs

- **Main App**: http://localhost:3000
- **API Health**: http://localhost:8000/api/health
- **API Docs**: http://localhost:8000/docs

## 🎯 Features to Test

✅ **Immediate Architecture Description**
✅ **File Upload with Validation**  
✅ **Dark/Light Mode Toggle**
✅ **Responsive Design**
✅ **Progress Tracking**
✅ **Mock Security Analysis** 
✅ **Results Export**
✅ **Copy to Clipboard**

The application is ready for testing! The new instant architecture description feature will show immediately after file upload.