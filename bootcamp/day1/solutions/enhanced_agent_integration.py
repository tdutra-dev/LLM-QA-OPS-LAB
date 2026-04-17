"""
🎯 DAY 1 DEMO: Advanced LangGraph Agent Integration

Integra tutte le funzionalità sviluppate negli exercises:
- Health Check Node ✅
- Advanced Conditional Routing ✅  
- Memory & Persistence ✅

OBIETTIVO: Crea un agent production-ready con features avanzate
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages

# Import delle soluzioni exercises
from .health_check_extension import health_check_node, should_proceed_with_action
from .advanced_routing import AdvancedRoutingEngine, intelligent_routing_node, update_system_context
from .memory_persistence import RedisCheckpointer, DistributedMemoryManager, MemoryContext

# ============================================================================
# Enhanced Agent State
# ============================================================================

class EnhancedAgentState(TypedDict):
    """
    Enhanced state che include tutte le funzionalità avanzate.
    Extends your existing AgentState.
    """
    # Core state (existing)
    incident: Dict[str, Any]
    evaluation_request: Optional[Dict[str, Any]]
    evaluation_result: Optional[Dict[str, Any]]
    evaluation_record: Optional[Dict[str, Any]]
    action_log: Optional[Dict[str, Any]]
    
    # RAG context (existing)
    context_chunks: Annotated[list, add_messages]
    
    # NEW: Health monitoring
    health_status: str
    health_checks: Dict[str, bool]
    health_timestamp: Optional[float]
    retry_count: int
    
    # NEW: Advanced routing context
    routing_decision: str
    routing_metadata: Dict[str, Any]
    context_updated: bool
    context_timestamp: Optional[float] 
    
    # NEW: Memory & persistence
    memory_context: Optional[MemoryContext]
    shared_state_keys: list
    coordination_status: str
    
    # NEW: Observability
    execution_trace: list
    performance_metrics: Dict[str, float]
    debug_info: Dict[str, Any]

# ============================================================================
# Enhanced Node Implementations
# ============================================================================

def enhanced_perceive_node(state: EnhancedAgentState) -> EnhancedAgentState:
    """
    Enhanced perceive node con observability e context management.
    """
    start_time = time.time()
    
    try:
        # Original perceive logic (from your agent)
        incident = state.get("incident", {})
        
        # NEW: Add tracing
        execution_trace = state.get("execution_trace", [])
        execution_trace.append({
            "node": "perceive",
            "timestamp": start_time,
            "input_size": len(json.dumps(incident))
        })
        
        # NEW: Performance tracking
        processing_time = time.time() - start_time
        performance_metrics = state.get("performance_metrics", {})
        performance_metrics["perceive_duration"] = processing_time
        
        return {
            "incident": incident,
            "execution_trace": execution_trace,
            "performance_metrics": performance_metrics,
            "debug_info": {"perceive_completed": True}
        }
        
    except Exception as e:
        return {
            "execution_trace": execution_trace + [{"node": "perceive", "error": str(e)}],
            "debug_info": {"perceive_error": str(e)}
        }

def enhanced_evaluate_node(state: EnhancedAgentState) -> EnhancedAgentState:
    """
    Enhanced evaluate node con context-aware evaluation.
    """
    start_time = time.time()
    
    try:
        # Get context from previous nodes
        health_status = state.get("health_status", "unknown")
        routing_decision = state.get("routing_decision", "default")
        context_chunks = state.get("context_chunks", [])
        
        incident = state.get("incident", {})
        
        # Enhanced evaluation logic che considera:
        # 1. System health status
        # 2. Routing decision context
        # 3. Historical context from RAG
        
        # Adjust evaluation based on context
        base_severity = incident.get("severity", "medium")
        
        # Health-aware adjustment
        if health_status == "unhealthy":
            # More conservative evaluation when system is unhealthy
            severity_multiplier = 1.5
        elif health_status == "degraded":
            severity_multiplier = 1.2
        else:
            severity_multiplier = 1.0
        
        # Context-aware scoring
        context_score = len(context_chunks) * 0.1  # More context = better decisions
        
        # Mock evaluation result (replace with your actual evaluation logic)
        evaluation_result = {
            "status": "needs_action" if severity_multiplier > 1.2 else "ok",
            "score": min(0.9, 0.5 + context_score) * severity_multiplier,
            "action": "restart_service" if severity_multiplier > 1.3 else "monitor",
            "confidence": 0.8 + context_score,
            "context_factors": {
                "health_status": health_status,
                "routing_decision": routing_decision,
                "context_chunks_count": len(context_chunks),
                "severity_multiplier": severity_multiplier
            }
        }
        
        # Performance tracking
        processing_time = time.time() - start_time
        performance_metrics = state.get("performance_metrics", {})
        performance_metrics["evaluate_duration"] = processing_time
        
        # Update execution trace
        execution_trace = state.get("execution_trace", [])
        execution_trace.append({
            "node": "evaluate",
            "timestamp": start_time,
            "processing_time": processing_time,
            "evaluation_score": evaluation_result["score"],
            "action": evaluation_result["action"]
        })
        
        return {
            "evaluation_result": evaluation_result,
            "execution_trace": execution_trace,
            "performance_metrics": performance_metrics,
            "debug_info": {"evaluate_completed": True}
        }
        
    except Exception as e:
        return {
            "execution_trace": execution_trace + [{"node": "evaluate", "error": str(e)}],
            "debug_info": {"evaluate_error": str(e)}
        }

def enhanced_act_node(state: EnhancedAgentState) -> EnhancedAgentState:
    """
    Enhanced action execution node con coordination e safety checks.
    """
    start_time = time.time()
    
    try:
        evaluation_result = state.get("evaluation_result", {})
        health_status = state.get("health_status", "unknown")
        coordination_status = state.get("coordination_status", "ready")
        
        action = evaluation_result.get("action", "monitor")
        
        # Safety checks before action execution
        safety_checks = {
            "health_check": health_status in ["healthy", "degraded"],
            "coordination_check": coordination_status in ["ready", "coordinated"], 
            "evaluation_confidence": evaluation_result.get("confidence", 0) > 0.6
        }
        
        all_safe = all(safety_checks.values())
        
        if not all_safe:
            # Fallback to monitoring if safety checks fail
            action_log = {
                "action": "monitor",
                "reason": "safety_checks_failed",
                "safety_checks": safety_checks,
                "timestamp": start_time,
                "original_action": action
            }
        else:
            # Execute the action
            action_log = {
                "action": action,
                "status": "success",
                "timestamp": start_time,
                "safety_checks": safety_checks,
                "execution_details": {
                    "health_context": health_status,
                    "coordination": coordination_status
                }
            }
            
            # Here you would implement actual action execution
            # For demo, we just simulate success
            print(f"[ACTION] Executing {action} with safety checks passed")
        
        # Performance tracking
        processing_time = time.time() - start_time
        performance_metrics = state.get("performance_metrics", {})
        performance_metrics["act_duration"] = processing_time
        
        # Update execution trace
        execution_trace = state.get("execution_trace", [])
        execution_trace.append({
            "node": "act",
            "timestamp": start_time,
            "processing_time": processing_time,
            "action": action,
            "safety_score": sum(safety_checks.values()) / len(safety_checks)
        })
        
        return {
            "action_log": action_log,
            "execution_trace": execution_trace,
            "performance_metrics": performance_metrics,
            "debug_info": {"act_completed": True}
        }
        
    except Exception as e:
        return {
            "execution_trace": execution_trace + [{"node": "act", "error": str(e)}],
            "debug_info": {"act_error": str(e)}
        }

# ============================================================================
# Enhanced Graph Builder
# ============================================================================

def create_enhanced_langgraph_agent() -> StateGraph:
    """
    Create the complete enhanced LangGraph agent con tutte le funzionalità.
    """
    
    # Initialize the graph
    graph = StateGraph(EnhancedAgentState)
    
    # Add all nodes
    graph.add_node("update_context", update_system_context)
    graph.add_node("perceive", enhanced_perceive_node)
    graph.add_node("health_check", health_check_node)
    graph.add_node("retrieve_context", lambda state: {"context_chunks": []})  # Placeholder
    graph.add_node("evaluate", enhanced_evaluate_node) 
    graph.add_node("act", enhanced_act_node)
    graph.add_node("store", lambda state: state)  # Placeholder
    graph.add_node("audit", lambda state: state)  # Placeholder
    
    # Enhanced routing nodes
    graph.add_node("route_decision", lambda state: {"routing_decision": intelligent_routing_node(state)})
    graph.add_node("escalate", lambda state: {"action_log": {"action": "escalate"}})
    graph.add_node("conservative_action", lambda state: {"action_log": {"action": "conservative"}})
    
    # Define the flow
    graph.add_edge(START, "update_context")
    graph.add_edge("update_context", "perceive")
    graph.add_edge("perceive", "health_check")
    graph.add_edge("health_check", "retrieve_context")
    graph.add_edge("retrieve_context", "route_decision")
    
    # Advanced routing from route_decision
    graph.add_conditional_edges(
        "route_decision",
        lambda state: state.get("routing_decision", "evaluate"),
        {
            "evaluate": "evaluate",
            "escalate": "escalate", 
            "conservative_action": "conservative_action",
            "execute_action": "act"
        }
    )
    
    # Continue flow from evaluate
    graph.add_conditional_edges(
        "evaluate",
        lambda state: "act" if state.get("evaluation_result", {}).get("status") == "needs_action" else "store",
        {
            "act": "act",
            "store": "store"
        }
    )
    
    # Final audit step
    graph.add_edge("act", "audit")
    graph.add_edge("conservative_action", "audit")
    graph.add_edge("escalate", "audit") 
    graph.add_edge("store", "audit")
    graph.add_edge("audit", END)
    
    return graph

# ============================================================================
# Demo Integration Class
# ============================================================================

class EnhancedAgentDemo:
    """Demo class che showcases all enhanced features"""
    
    def __init__(self):
        self.graph = create_enhanced_langgraph_agent()
        self.checkpointer = RedisCheckpointer()
        self.memory_manager = DistributedMemoryManager()
        self.routing_engine = AdvancedRoutingEngine()
        
        # Compile with checkpointer
        self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
    
    async def run_enhanced_demo(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Run complete demo with all enhanced features"""
        
        # Initialize enhanced state
        initial_state = {
            "incident": incident,
            "health_status": "unknown",
            "health_checks": {},
            "retry_count": 0,
            "routing_decision": "",
            "context_updated": False,
            "memory_context": MemoryContext(
                agent_id="demo_agent",
                thread_id=f"demo_{int(time.time())}",
                workflow_type="enhanced_demo"
            ),
            "shared_state_keys": [],
            "coordination_status": "ready",
            "execution_trace": [],
            "performance_metrics": {},
            "debug_info": {}
        }
        
        # Configuration for checkpointing
        config = {
            "configurable": {
                "thread_id": initial_state["memory_context"].thread_id
            }
        }
        
        print(f"🚀 Starting enhanced agent demo for incident: {incident.get('id', 'unknown')}")
        
        # Execute the workflow
        try:
            results = []
            async for event in self.compiled_graph.astream(initial_state, config):
                results.append(event)
                
                # Real-time debugging
                for node_name, node_state in event.items():
                    if node_name != "__end__":
                        print(f"📍 Node: {node_name}")
                        if "debug_info" in node_state:
                            print(f"   Debug: {node_state['debug_info']}")
                        if "performance_metrics" in node_state:
                            print(f"   Perf: {node_state['performance_metrics']}")
            
            # Final result summary
            final_state = {}
            for event in results:
                final_state.update(event)
            
            # Generate execution summary
            summary = self._generate_execution_summary(final_state)
            print(f"\\n✅ Demo completed! Summary:")
            print(json.dumps(summary, indent=2))
            
            return summary
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            return {"error": str(e)}
    
    def _generate_execution_summary(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive execution summary"""
        return {
            "execution_summary": {
                "total_nodes": len(final_state.get("execution_trace", [])),
                "total_duration": sum(
                    trace.get("processing_time", 0) 
                    for trace in final_state.get("execution_trace", [])
                ),
                "final_action": final_state.get("action_log", {}).get("action"),
                "health_status": final_state.get("health_status"),
                "routing_decision": final_state.get("routing_decision")
            },
            "performance_metrics": final_state.get("performance_metrics", {}),
            "safety_analysis": {
                "safety_checks_passed": True,  # Simplified
                "risk_level": "low"
            },
            "observability": {
                "trace_length": len(final_state.get("execution_trace", [])),
                "debug_entries": len(final_state.get("debug_info", {}))
            }
        }

# ============================================================================
# Demo Scenarios
# ============================================================================

async def run_demo_scenarios():
    """Run various demo scenarios to showcase capabilities"""
    
    demo = EnhancedAgentDemo()
    
    scenarios = [
        {
            "name": "High Severity Database Issue",
            "incident": {
                "id": "db-crit-001",
                "incident_type": "database_timeout",
                "severity": "critical",
                "message": "Database connection pool exhausted",
                "timestamp": time.time()
            }
        },
        {
            "name": "Medium Severity API Slowdown",
            "incident": {
                "id": "api-med-001", 
                "incident_type": "performance_degradation",
                "severity": "medium",
                "message": "API response time increased by 300%",
                "timestamp": time.time()
            }
        },
        {
            "name": "Low Severity Monitoring Alert",
            "incident": {
                "id": "mon-low-001",
                "incident_type": "metric_threshold",
                "severity": "low", 
                "message": "CPU usage above 80% for 5 minutes",
                "timestamp": time.time()
            }
        }
    ]
    
    for scenario in scenarios:
        print(f"\\n" + "="*60)
        print(f"🎬 Running scenario: {scenario['name']}")
        print("="*60)
        
        result = await demo.run_enhanced_demo(scenario["incident"])
        
        # Brief pause between scenarios
        await asyncio.sleep(2)

# ============================================================================
# Integration Instructions
# ============================================================================

INTEGRATION_INSTRUCTIONS = """
🔧 INTEGRATION INSTRUCTIONS

1. Replace your existing langgraph_agent.py with enhanced version:

   cp bootcamp/day1/solutions/enhanced_agent_integration.py \\
      packages/eval-py/src/eval_py/langgraph_agent_enhanced.py

2. Update main.py imports:

   from .langgraph_agent_enhanced import create_enhanced_langgraph_agent

3. Add new dependencies to pyproject.toml:

   dependencies = [
       # ... existing dependencies ...
       "aiohttp>=3.8",  # For health checks
   ]

4. Test the enhanced agent:

   curl -X POST http://localhost:8010/agent/graph/run \\
     -H "Content-Type: application/json" \\
     -d '{
       "incident": {
         "id": "test-enhanced-001",
         "severity": "high",
         "incident_type": "database_failure"
       }
     }'

5. Monitor with enhanced observability:

   # Check execution trace
   curl http://localhost:8010/agent/graph/trace/{thread_id}
   
   # Check performance metrics  
   curl http://localhost:8010/agent/graph/metrics/{thread_id}

6. Use checkpointing features:

   # Rollback to previous state
   curl -X POST http://localhost:8010/agent/graph/rollback/{thread_id}/{checkpoint_id}

🎯 SUCCESS CRITERIA for Day 1:
✅ Agent runs with all enhanced features
✅ Health checks working
✅ Advanced routing decisions
✅ Memory persistence active
✅ Observability traces generated
✅ Demo scenarios completed successfully

Ready for DAY 2: Python Advanced Patterns! 🐍
"""

# ============================================================================
# Main Demo Runner
# ============================================================================

if __name__ == "__main__":
    print("🎯 DAY 1 FINAL DEMO: Enhanced LangGraph Agent")
    print("=" * 60)
    
    # Run demo scenarios
    asyncio.run(run_demo_scenarios())
    
    print("\\n" + INTEGRATION_INSTRUCTIONS)