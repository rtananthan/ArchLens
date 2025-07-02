#!/bin/bash

# Local development setup script
set -e

echo "🛠️  Setting up ArchLens for local development..."

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker is not installed (optional for backend development)"
fi

echo "✅ Prerequisites check passed"

# Setup backend
echo "🐍 Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing backend dependencies..."
pip install -r requirements.txt

echo "✅ Backend setup completed"
deactivate
cd ..

# Setup frontend
echo "🎨 Setting up frontend..."
cd frontend

# Install dependencies
echo "Installing frontend dependencies..."
npm install

echo "✅ Frontend setup completed"
cd ..

# Setup infrastructure
echo "🏗️  Setting up infrastructure..."
cd infrastructure

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating CDK virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing CDK dependencies..."
pip install -r requirements.txt

echo "✅ Infrastructure setup completed"
deactivate
cd ..

# Create environment files
echo "📝 Creating environment files..."

# Backend environment
cat > backend/.env << EOF
# Local development environment
UPLOAD_BUCKET=local-test-bucket
ANALYSIS_TABLE=local-test-table
BEDROCK_AGENT_ID=local-test-agent
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
AWS_REGION=us-east-1
EOF

# Frontend environment
cat > frontend/.env.local << EOF
# Local development environment
NEXT_PUBLIC_API_URL=http://localhost:8000/api
EOF

echo "✅ Environment files created"

echo ""
echo "🎉 Local development setup completed!"
echo ""
echo "🚀 To start development:"
echo ""
echo "Backend (Terminal 1):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn src.handlers.api:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Frontend (Terminal 2):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "Or use Docker for backend:"
echo "   cd backend"
echo "   docker build -t archlens-backend ."
echo "   docker run -p 8000:8000 archlens-backend"
echo ""
echo "📝 Note: For full functionality, you'll need to deploy the infrastructure first"
echo "   or mock the AWS services for local testing."