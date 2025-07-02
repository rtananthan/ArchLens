#!/bin/bash

# Local development startup script
echo "🚀 Starting ArchLens Local Development Environment..."

# Check if backend virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "❌ Backend virtual environment not found. Please run ./scripts/local-dev.sh first"
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Frontend dependencies not found. Please run ./scripts/local-dev.sh first"
    exit 1
fi

echo "📋 Starting services..."

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait
    echo "✅ Services stopped"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start backend mock server
echo "🐍 Starting backend mock server on http://localhost:8000..."
cd backend
source venv/bin/activate
python mock_server.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend
echo "🎨 Starting frontend on http://localhost:3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait a moment for frontend to start
sleep 3

echo ""
echo "🎉 ArchLens Local Development Ready!"
echo ""
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "🧪 Test Features:"
echo "   • Upload the sample file: examples/sample-aws-architecture.xml"
echo "   • See immediate architecture description"
echo "   • Watch mock analysis progress (completes in ~15 seconds)"
echo "   • View mock security results"
echo ""
echo "💡 Press Ctrl+C to stop all services"
echo ""

# Wait for background processes
wait