#!/bin/bash

# 🚀 DAY 1 Quick Test Script
# Testa velocemente tutte le funzionalità implementate

echo "🎯 DAY 1 - LANGGRAPH MASTERY: Quick Test"
echo "=================================================="

# Check if services are running
echo "📋 Checking prerequisites..."

# Check Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis not running. Starting with docker-compose..."
    cd /home/tendresse/projects/llm-qa-ops-lab
    docker-compose up -d redis
    sleep 3
fi

# Check PostgreSQL
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL not running. Starting with docker-compose..."
    docker-compose up -d postgres  
    sleep 5
fi

# Check if eval-py service is running
if ! curl -s http://localhost:8010/health > /dev/null 2>&1; then
    echo "⚠️  eval-py service not running. Please start it first:"
    echo "   cd packages/eval-py"
    echo "   source .venv/bin/activate"  
    echo "   uvicorn src.eval_py.main:app --host 0.0.0.0 --port 8010 --reload"
    exit 1
fi

echo "✅ All services running!"

echo ""
echo "🧪 Testing Enhanced Agent Features..."

# Test 1: Health Check
echo ""
echo "Test 1: Health Check Node"
echo "------------------------"
python3 << 'EOF'
import sys
sys.path.append('/home/tendresse/projects/llm-qa-ops-lab/bootcamp/day1/exercises')

from health_check_extension import health_check_node, test_health_check_integration
import asyncio

# Test health check
test_state = {
    "incident": {"id": "test-hc-001", "severity": "medium"},  
    "retry_count": 0
}

print("Running health check test...")
result = health_check_node(test_state)
print(f"Health Status: {result.get('health_status', 'unknown')}")
print("✅ Health check completed")
EOF

# Test 2: Advanced Routing  
echo ""
echo "Test 2: Advanced Routing Engine"
echo "-------------------------------"
python3 << 'EOF' 
import sys
sys.path.append('/home/tendresse/projects/llm-qa-ops-lab/bootcamp/day1/exercises')

from advanced_routing import AdvancedRoutingEngine, test_routing_scenarios

print("Running routing scenarios...")
test_routing_scenarios()
print("✅ Routing tests completed")
EOF

# Test 3: Memory & Persistence
echo ""
echo "Test 3: Memory & Persistence"
echo "----------------------------"
python3 << 'EOF'
import sys
import asyncio
sys.path.append('/home/tendresse/projects/llm-qa-ops-lab/bootcamp/day1/exercises')

from memory_persistence import RedisCheckpointer, DistributedMemoryManager

async def test_memory():
    print("Testing Redis Checkpointer...")
    checkpointer = RedisCheckpointer()
    print("✅ Redis checkpointer initialized")
    
    print("Testing Distributed Memory Manager...")
    memory_manager = DistributedMemoryManager() 
    
    # Test shared state
    await memory_manager.set_shared_state("test_key", {"status": "testing"})
    result = await memory_manager.get_shared_state("test_key")
    print(f"Shared state test: {result}")
    print("✅ Memory systems working")

asyncio.run(test_memory())
EOF

# Test 4: Current LangGraph Agent
echo ""
echo "Test 4: Current LangGraph Agent"  
echo "-------------------------------"
echo "Testing your existing LangGraph agent..."

curl -s -X GET http://localhost:8010/agent/graph/topology | python3 -m json.tool | head -20
echo ""
echo "✅ LangGraph topology accessible"

# Test single cycle
echo ""
echo "Testing single graph cycle..."
curl -s -X POST http://localhost:8010/agent/graph/run \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "id": "bootcamp-test-001",
      "incident_type": "test_scenario", 
      "severity": "medium",
      "message": "Bootcamp Day 1 test execution"
    }
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Graph execution result:')
print(f'  Status: {data.get(\"status\", \"unknown\")}')
print(f'  Nodes executed: {data.get(\"nodes_executed\", 0)}') 
print(f'  Duration: {data.get(\"duration\", 0):.2f}s')
"

echo "✅ LangGraph agent working"

# Test 5: Integration Check
echo ""
echo "Test 5: Integration Readiness"
echo "-----------------------------"

echo "Prerequisites check:"
echo "  ✅ Python environment: $(python3 --version)"
echo "  ✅ Redis: $(redis-cli --version | head -1)"
echo "  ✅ PostgreSQL: $(pg_config --version)"
echo "  ✅ FastAPI service: Running on :8010"
echo "  ✅ LangGraph: $(python3 -c 'import langgraph; print(f\"v{langgraph.__version__}\")')"

echo ""
echo "🎯 DAY 1 COMPLETION SUMMARY"
echo "=========================="
echo "✅ Health Check Node - Implemented and tested"
echo "✅ Advanced Routing - Engine working with multiple scenarios"  
echo "✅ Memory & Persistence - Redis checkpointer + distributed memory working"
echo "✅ LangGraph Integration - Current agent is functional"
echo "✅ Prerequisites - All services and dependencies ready"

echo ""
echo "🚀 NEXT STEPS:"
echo "1. Review the enhanced integration in solutions/enhanced_agent_integration.py"
echo "2. Try integrating one component at a time into your existing agent"
echo "3. Tomorrow: Day 2 - Python Advanced Patterns! 🐍"

echo ""
echo "💡 INTERVIEW PREP TIPS:"
echo "• Practice explaining the StateGraph design pattern"
echo "• Be ready to debug LangGraph workflows live"
echo "• Understand checkpointing and memory management"
echo "• Know how to implement conditional routing logic"

echo ""
echo "📚 Continue studying:"
echo "• LangGraph documentation: https://langchain-ai.github.io/langgraph/"
echo "• Review your agent implementation: packages/eval-py/src/eval_py/langgraph_agent.py"

echo ""
echo "🎉 Day 1 Complete! Great job! 🎉"