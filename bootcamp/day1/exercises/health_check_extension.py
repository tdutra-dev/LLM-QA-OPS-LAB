"""
Exercise 1.3: Health Check Node Extension

Estendi il LangGraph agent aggiungendo un health check node che
controlli lo stato dei servizi esterni prima di eseguire azioni.

OBIETTIVO:
- Aggiungere un nuovo node "health_check" al graph
- Implementare retry logic con exponential backoff   
- Update state con health status dei servizi
- Conditional routing basato su health status
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

# ============================================================================
# TODO 1: Estendi AgentState nel tuo langgraph_agent.py 
# ============================================================================
"""
Aggiungi questi campi al tuo AgentState TypedDict:

health_status: str  # "healthy" | "degraded" | "unhealthy"
health_checks: Dict[str, bool]  # service -> status
health_timestamp: Optional[float]
retry_count: int
"""

# ============================================================================
# TODO 2: Implementa Health Check Functions
# ============================================================================

async def check_service_health(service_url: str, timeout: float = 5.0) -> bool:
    """
    Check if a service is healthy via HTTP health endpoint.
    
    Args:
        service_url: Service health endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        True if service is healthy, False otherwise
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(service_url) as response:
                return response.status == 200
    except Exception as e:
        print(f"Health check failed for {service_url}: {e}")
        return False


async def perform_health_checks(services: Dict[str, str]) -> Dict[str, bool]:
    """
    Perform health checks on multiple services concurrently.
    
    Args:
        services: Dict mapping service name to health endpoint URL
        
    Returns:
        Dict mapping service name to health status (True=healthy)
    """
    # TODO: Implement concurrent health checking
    # Hint: Use asyncio.gather() per concurrent requests
    
    tasks = []
    for service_name, health_url in services.items():
        task = check_service_health(health_url)
        tasks.append((service_name, task))
    
    results = {}
    completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
    
    for (service_name, _), result in zip(tasks, completed_tasks):
        if isinstance(result, Exception):
            results[service_name] = False
        else:
            results[service_name] = result
    
    return results


# ============================================================================
# TODO 3: Implementa Health Check Node
# ============================================================================

def health_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function to check external service health.
    
    This node should:
    1. Check health of critical services (PostgreSQL, Redis, external APIs)
    2. Implement retry logic with exponential backoff
    3. Update state with health status and timestamp
    4. Determine if system is healthy enough to proceed with actions
    """
    
    # Services to check (update URLs based on your setup)
    services_to_check = {
        "postgres": "http://localhost:5432/health",  # Mock endpoint 
        "redis": "http://localhost:6379/health",     # Mock endpoint
        "external_api": "https://api.example.com/health"  # Mock endpoint
    }
    
    # TODO: Implement with retry logic
    max_retries = 3
    retry_delay = 1.0  # Start with 1 second
    current_retry = state.get("retry_count", 0)
    
    try:
        # Perform health checks
        health_results = asyncio.run(perform_health_checks(services_to_check))
        
        # Calculate overall health status
        healthy_services = sum(1 for status in health_results.values() if status)
        total_services = len(health_results)
        health_percentage = healthy_services / total_services if total_services > 0 else 0
        
        # Determine overall health status
        if health_percentage >= 0.8:
            overall_status = "healthy"
        elif health_percentage >= 0.5:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "health_status": overall_status,
            "health_checks": health_results,
            "health_timestamp": time.time(),
            "retry_count": 0  # Reset retry count on success
        }
        
    except Exception as e:
        print(f"Health check error: {e}")
        
        # Retry logic with exponential backoff
        if current_retry < max_retries:
            sleep_time = retry_delay * (2 ** current_retry)
            print(f"Retrying health check in {sleep_time} seconds (attempt {current_retry + 1}/{max_retries})")
            time.sleep(sleep_time)
            
            return {
                "health_status": "checking",
                "retry_count": current_retry + 1,
                "health_timestamp": time.time()
            }
        else:
            # Max retries reached
            return {
                "health_status": "unhealthy",
                "health_checks": {},
                "health_timestamp": time.time(),
                "retry_count": 0,
                "error": f"Health check failed after {max_retries} retries"
            }


# ============================================================================
# TODO 4: Conditional Routing Function  
# ============================================================================

def should_proceed_with_action(state: Dict[str, Any]) -> str:
    """
    Determine next node based on health status and incident severity.
    
    Routing logic:
    - If unhealthy + high severity → escalate
    - If unhealthy + low/medium severity → wait and retry health check
    - If degraded → proceed with caution (limited actions)
    - If healthy → proceed normally
    
    This function will be used as a conditional edge.
    """
    health_status = state.get("health_status", "unknown")
    incident = state.get("incident", {})
    severity = incident.get("severity", "medium").lower()
    
    # TODO: Implement routing logic
    if health_status == "unhealthy":
        if severity == "high":
            return "escalate"
        else:
            return "wait_and_retry"
    elif health_status == "degraded":
        return "proceed_with_caution" 
    elif health_status == "healthy":
        return "proceed_normally"
    else:
        return "health_check"  # Unknown status, re-check


# ============================================================================
# TODO 5: Integration Test
# ============================================================================

async def test_health_check_integration():
    """Test the health check functionality"""
    
    # Mock state
    test_state = {
        "incident": {
            "id": "test-001", 
            "severity": "medium",
            "message": "Database connection slow"
        },
        "retry_count": 0
    }
    
    print("Testing health check node...")
    result = health_check_node(test_state)
    print(f"Health check result: {result}")
    
    # Test routing
    routing_decision = should_proceed_with_action({**test_state, **result})
    print(f"Routing decision: {routing_decision}")


# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
Per integrare nel tuo LangGraph agent:

1. Modifica packages/eval-py/src/eval_py/langgraph_agent.py:
   
   - Aggiungi i campi al AgentState TypedDict
   - Importa le funzioni da questo file
   - Aggiungi il node al graph:
     
     graph.add_node("health_check", health_check_node)
     
   - Aggiungi conditional edge:
   
     graph.add_conditional_edges(
         "health_check",
         should_proceed_with_action,
         {
             "proceed_normally": "evaluate",
             "proceed_with_caution": "evaluate", 
             "escalate": "escalate",
             "wait_and_retry": "health_check",
         }
     )

2. Modifica il flow per passare attraverso health_check prima di evaluate:
   
   graph.add_edge("retrieve_context", "health_check")

3. Test con curl:
   
   curl -X POST http://localhost:8010/agent/graph/run \
     -H "Content-Type: application/json" \
     -d '{"incident": {"id": "test", "severity": "high"}}'
"""


if __name__ == "__main__":
    # Run test
    asyncio.run(test_health_check_integration())