#!/bin/bash

echo "🚀 Starting SIMBA Development Environment"
echo "========================================"

if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please create a .env file with required environment variables."
    exit 1
fi

echo "🛑 Stopping existing containers..."
docker compose down -v

echo "🏗️  Building and starting containers..."
docker compose up --build -d

echo "⏳ Waiting for services to start..."
sleep 10

echo "🔍 Checking service status..."
docker compose ps

echo "🌐 Testing web service..."
if curl -s http://localhost:8000 > /dev/null; then
    echo "✅ Web service is responding at http://localhost:8000"
else
    echo "❌ Web service is not responding"
fi

echo "🤖 Testing Chainlit service..."
if curl -s http://localhost:8500 > /dev/null; then
    echo "✅ Chainlit service is responding at http://localhost:8500"
else
    echo "❌ Chainlit service is not responding"
    echo "📋 Chainlit logs:"
    docker compose logs chainlit | tail -20
fi

echo ""
echo "🎉 Development environment is ready!"
echo "📝 Useful commands:"
echo "   make logs           - View all logs"
echo "   make logs-chainlit  - View Chainlit logs"
echo "   make logs-web       - View web logs"
echo "   make status         - Check container status"
echo "   make restart        - Restart web service"
echo ""
echo "🌍 Access the application:"
echo "   Web: http://localhost:8000"
echo "   Chainlit: http://localhost:8500" 