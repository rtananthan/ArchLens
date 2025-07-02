# Local Testing Guide

✅ **ArchLens is now running locally!**

## 🌐 Access URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs

## 🧪 Testing the New Architecture Description Feature

### 1. Open the Application
Navigate to http://localhost:3000 in your browser

### 2. Upload Test File
- Use the provided sample file: `examples/sample-aws-architecture.xml`
- Drag and drop it onto the upload area, or click to select

### 3. See Immediate Description
After upload, you should immediately see:
- **Architecture Description card** with a detailed English explanation
- Information about detected AWS services
- Architecture patterns identified
- Data flow description
- Security aspects highlighted

### 4. Continue to Mock Analysis
- Click "Continue to Security Analysis"
- Watch the progress indicator (mock analysis takes ~15 seconds)
- See the final results with both description and security analysis

## 🎯 Features to Test

### ✅ Instant Architecture Description
- **Service Detection**: Should identify all AWS services in the diagram
- **Pattern Recognition**: Detects patterns like "Load-balanced web application"
- **Data Flow**: Describes how traffic flows through the architecture
- **Security Aspects**: Highlights security-relevant services
- **Copy Functionality**: Test the copy button to copy description text

### ✅ UI Components
- **Dark/Light Mode**: Toggle in the top-right corner
- **Responsive Design**: Test on different screen sizes
- **File Upload**: Drag-and-drop and click-to-select
- **Progress Tracking**: Real-time updates during analysis
- **Results Dashboard**: Interactive display of findings

### ✅ Mock Analysis Results
The mock server provides realistic security analysis results:
- **Overall Score**: 7.2/10
- **Security Issues**: HIGH, MEDIUM, LOW severity items
- **Recommendations**: Actionable security improvements
- **Export**: JSON export functionality

## 🔧 Development Features

### Hot Reload
- Frontend changes automatically refresh
- Backend changes require restart

### API Testing
- Visit http://localhost:8000/docs for interactive API documentation
- Test endpoints directly from the browser

### File Upload Testing
- Try different file types (should reject non-XML files)
- Test large files (10MB+ should be rejected)
- Test malformed XML (should show error handling)

## 🐛 Troubleshooting

### Frontend Issues
```bash
cd frontend
npm run dev
```

### Backend Issues
```bash
cd backend
source venv/bin/activate
python mock_server.py
```

### Port Conflicts
- Frontend uses port 3000
- Backend uses port 8000
- Change ports in scripts if needed

## 🎨 Testing Checklist

- [ ] Upload sample architecture file
- [ ] See immediate architecture description
- [ ] Copy description text to clipboard
- [ ] Continue to security analysis
- [ ] Watch progress indicator
- [ ] View complete results
- [ ] Export results as JSON
- [ ] Toggle dark/light mode
- [ ] Test responsive design
- [ ] Try error scenarios (wrong file type)

## 📝 Expected Architecture Description Output

For the sample file, you should see something like:

```
**AWS Security Architecture**

This architecture diagram contains 10 AWS services with 5 connections between components.

The architecture includes: 1 Internet Gateway, 1 VPC network, 1 Load Balancer, 1 EC2 instance, 1 RDS database, 1 S3 bucket, 1 Lambda function, 1 API Gateway, 1 DynamoDB table, and 1 CloudWatch monitoring.

Architecture Patterns Detected: Load-balanced web application, Serverless API, Multi-tier data storage

Data Flow: Traffic enters through Internet Gateway and flows to DynamoDB table.

Security Aspects: Includes VPC network isolation, CloudWatch monitoring.
```

## 🚀 Next Steps

After testing locally:
1. Review the architecture description accuracy
2. Test with your own draw.io files
3. Consider deploying to AWS for full functionality
4. Customize the analysis patterns as needed

The local mock environment gives you full UI functionality without requiring AWS infrastructure!