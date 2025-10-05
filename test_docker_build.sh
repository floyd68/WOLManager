#!/bin/bash

echo "Testing Docker build configuration..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Docker not available - checking Dockerfile syntax instead"
    
    # Check if the Dockerfile exists and has the right content
    if [ -f "Dockerfile" ]; then
        echo "✅ Dockerfile exists"
        
        # Check if it uses Python 3.13
        if grep -q "FROM python:3.13-slim" Dockerfile; then
            echo "✅ Uses Python 3.13"
        else
            echo "❌ Not using Python 3.13"
        fi
        
        # Check if SNMP packages are removed
        if ! grep -q "libsnmp-dev" Dockerfile; then
            echo "✅ SNMP packages removed"
        else
            echo "❌ SNMP packages still present"
        fi
        
        # Check if curl is included
        if grep -q "curl" Dockerfile; then
            echo "✅ curl included for health checks"
        else
            echo "❌ curl not included"
        fi
    else
        echo "❌ Dockerfile not found"
    fi
    
    # Check docker-compose.yml
    if [ -f "docker-compose.yml" ]; then
        echo "✅ docker-compose.yml exists"
        
        # Check if early termination settings are included
        if grep -q "DISCOVERY_EARLY_TERMINATION" docker-compose.yml; then
            echo "✅ Early termination settings included"
        else
            echo "❌ Early termination settings missing"
        fi
    else
        echo "❌ docker-compose.yml not found"
    fi
    
else
    echo "Docker available - testing build..."
    docker build -t wolmanager-test .
    
    if [ $? -eq 0 ]; then
        echo "✅ Docker build successful"
        docker rmi wolmanager-test  # Clean up
    else
        echo "❌ Docker build failed"
    fi
fi

echo "Test completed"
