"""
Exercise 1.4: Advanced Conditional Routing

Implementa routing condizionale sofisticato basato su:
- Severità dell'incident
- Health status dei servizi  
- Storico performance
- Carico di lavoro attuale

OBIETTIVO: Creare decision logic intelligent che ottimizza il workflow
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import time
import json

# ============================================================================
# Data Models per Routing
# ============================================================================

class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class ActionType(Enum):
    RESTART = "restart"
    SCALE = "scale"
    ALERT = "alert"
    ESCALATE = "escalate"
    MONITOR = "monitor"
    ROLLBACK = "rollback"

class WorkloadLevel(Enum):
    LOW = "low"      # < 30% capacity
    NORMAL = "normal" # 30-70% capacity
    HIGH = "high"    # 70-90% capacity
    OVERLOAD = "overload" # > 90% capacity

# ============================================================================
# TODO 1: Implementa Context Analyzer
# ============================================================================

class SystemContext:
    """Analizza il contesto corrente del sistema per decision making"""
    
    def __init__(self):
        self.performance_history: List[Dict] = []
        self.active_incidents: List[Dict] = []
        self.resource_metrics: Dict[str, float] = {}
    
    def get_current_workload(self) -> WorkloadLevel:
        """
        Analizza metriche correnti per determinare workload level.
        In produzione, questo dovrebbe integrare con Prometheus.
        """
        # TODO: Implement based on current metrics
        cpu_usage = self.resource_metrics.get("cpu_usage_percent", 50.0)
        memory_usage = self.resource_metrics.get("memory_usage_percent", 60.0)
        active_requests = self.resource_metrics.get("active_requests", 100)
        
        # Calculate combined load score
        load_score = (cpu_usage + memory_usage) / 2
        
        if load_score < 30:
            return WorkloadLevel.LOW
        elif load_score < 70:
            return WorkloadLevel.NORMAL
        elif load_score < 90:
            return WorkloadLevel.HIGH
        else:
            return WorkloadLevel.OVERLOAD
    
    def get_similar_incidents_count(self, incident: Dict[str, Any], hours: int = 24) -> int:
        """Count similar incidents in the last N hours"""
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        incident_type = incident.get("incident_type", "")
        similar_count = 0
        
        for hist_incident in self.performance_history:
            if (hist_incident.get("timestamp", 0) > cutoff_time and 
                hist_incident.get("incident_type") == incident_type):
                similar_count += 1
        
        return similar_count
    
    def get_escalation_trend(self) -> str:
        """Analyze if incidents are trending towards escalation"""
        recent_incidents = [
            inc for inc in self.performance_history 
            if inc.get("timestamp", 0) > time.time() - 3600  # Last hour
        ]
        
        if len(recent_incidents) == 0:
            return "stable"
        
        escalated_count = sum(1 for inc in recent_incidents if inc.get("escalated", False))
        escalation_rate = escalated_count / len(recent_incidents)
        
        if escalation_rate > 0.5:
            return "deteriorating"
        elif escalation_rate > 0.2:
            return "concerning"
        else:
            return "stable"

# ============================================================================
# TODO 2: Advanced Routing Engine
# ============================================================================

class AdvancedRoutingEngine:
    """
    Routing engine intelligente che considera multipli fattori per
    decidere il next step nel workflow.
    """
    
    def __init__(self):
        self.context = SystemContext()
        self.routing_rules = self._load_routing_rules()
    
    def _load_routing_rules(self) -> List[Dict]:
        """
        Carica regole di routing configurabili.
        In produzione, queste potrebbero venire da database o config files.
        """
        return [
            {
                "name": "critical_incident_fast_track",
                "conditions": {
                    "severity": ["critical"],
                    "health_status": ["healthy", "degraded"]
                },
                "action": "direct_action",
                "priority": 1
            },
            {
                "name": "high_load_cautious",
                "conditions": {
                    "workload": ["high", "overload"],
                    "severity": ["medium", "high"]
                },
                "action": "staged_execution",
                "priority": 2
            },
            {
                "name": "repeated_incident_escalation",
                "conditions": {
                    "similar_incidents_1h": 3  # 3+ similar in last hour
                },
                "action": "escalate",
                "priority": 1
            },
            {
                "name": "degraded_system_conservative",
                "conditions": {
                    "health_status": ["degraded", "unhealthy"]
                },
                "action": "conservative_approach",
                "priority": 3
            }
        ]
    
    def determine_routing(self, state: Dict[str, Any]) -> str:
        """
        Main routing function - determina next step basato su state completo.
        
        Returns:
            Next node name nel LangGraph workflow
        """
        # Extract state components
        incident = state.get("incident", {})
        health_status = state.get("health_status", "unknown")
        
        # Analyze current context
        severity = Severity(incident.get("severity", "medium"))
        health = HealthStatus(health_status)
        workload = self.context.get_current_workload()
        
        # Build decision context
        decision_context = {
            "severity": severity.value,
            "health_status": health.value,
            "workload": workload.value,
            "similar_incidents_1h": self.context.get_similar_incidents_count(incident, 1),
            "similar_incidents_24h": self.context.get_similar_incidents_count(incident, 24),
            "escalation_trend": self.context.get_escalation_trend()
        }
        
        # Apply routing rules
        applicable_rule = self._find_best_rule(decision_context)
        
        if applicable_rule:
            action = applicable_rule["action"]
            return self._map_action_to_node(action, decision_context)
        
        # Default routing
        return self._default_routing(decision_context)
    
    def _find_best_rule(self, context: Dict[str, Any]) -> Optional[Dict]:
        """Find the best matching routing rule"""
        matching_rules = []
        
        for rule in self.routing_rules:
            if self._rule_matches(rule["conditions"], context):
                matching_rules.append(rule)
        
        if not matching_rules:
            return None
        
        # Sort by priority (lower number = higher priority)
        return min(matching_rules, key=lambda r: r["priority"])
    
    def _rule_matches(self, conditions: Dict, context: Dict[str, Any]) -> bool:
        """Check if a routing rule matches the current context"""
        for condition_key, condition_values in conditions.items():
            context_value = context.get(condition_key)
            
            if isinstance(condition_values, list):
                if context_value not in condition_values:
                    return False
            elif isinstance(condition_values, (int, float)):
                if context_value < condition_values:
                    return False
            
        return True
    
    def _map_action_to_node(self, action: str, context: Dict[str, Any]) -> str:
        """Map routing action to actual LangGraph node name"""
        mapping = {
            "direct_action": "execute_action",
            "staged_execution": "prepare_staged_action", 
            "escalate": "escalate_incident",
            "conservative_approach": "conservative_action",
            "monitor_only": "monitor_and_wait"
        }
        
        return mapping.get(action, "evaluate")  # fallback to evaluate
    
    def _default_routing(self, context: Dict[str, Any]) -> str:
        """Default routing quando no rules match"""
        severity = context["severity"]
        health_status = context["health_status"]
        
        if severity == "critical":
            return "execute_action"
        elif health_status in ["unhealthy", "degraded"]:
            return "conservative_action"
        else:
            return "evaluate"

# ============================================================================
# TODO 3: LangGraph Integration Functions
# ============================================================================

# Global routing engine instance
routing_engine = AdvancedRoutingEngine()

def intelligent_routing_node(state: Dict[str, Any]) -> str:
    """
    LangGraph conditional edge function using advanced routing.
    
    This replaces simple routing logic with intelligent decision making.
    """
    try:
        next_node = routing_engine.determine_routing(state)
        
        # Log routing decision for observability
        incident_id = state.get("incident", {}).get("id", "unknown")
        print(f"[ROUTING] Incident {incident_id} → {next_node}")
        
        return next_node
        
    except Exception as e:
        print(f"[ROUTING ERROR] {e}")
        return "evaluate"  # Safe fallback

def update_system_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node che aggiorna system context con le informazioni correnti.
    Questo should essere chiamato early nel workflow.
    """
    # Update resource metrics (in produzione, pull from Prometheus)
    routing_engine.context.resource_metrics = {
        "cpu_usage_percent": 65.0,  # Mock values
        "memory_usage_percent": 78.0,
        "active_requests": 150,
        "response_time_ms": 250
    }
    
    # Add current incident to history
    incident = state.get("incident")
    if incident:
        routing_engine.context.performance_history.append({
            **incident,
            "timestamp": time.time(),
            "processed_by": "langgraph_agent"
        })
    
    return {
        "context_updated": True,
        "context_timestamp": time.time()
    }

# ============================================================================
# TODO 4: Testing e Validation
# ============================================================================

def test_routing_scenarios():
    """Test various routing scenarios"""
    
    test_cases = [
        {
            "name": "Critical incident, healthy system",
            "state": {
                "incident": {"severity": "critical", "id": "crit-001"},
                "health_status": "healthy"
            },
            "expected": "execute_action"
        },
        {
            "name": "Medium incident, degraded system",
            "state": {
                "incident": {"severity": "medium", "id": "med-001"},
                "health_status": "degraded"
            },
            "expected": "conservative_action"
        },
        {
            "name": "Repeated incident pattern",
            "state": {
                "incident": {"severity": "low", "incident_type": "timeout", "id": "rep-001"},
                "health_status": "healthy"
            },
            "expected": "escalate"  # After simulating repeated incidents
        }
    ]
    
    for test_case in test_cases:
        print(f"\\nTesting: {test_case['name']}")
        result = intelligent_routing_node(test_case["state"])
        print(f"Expected: {test_case['expected']}, Got: {result}")

# ============================================================================ 
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
Per integrare advanced routing nel tuo LangGraph:

1. Modifica langgraph_agent.py:

   # Aggiungi context update node
   graph.add_node("update_context", update_system_context)
   
   # Modifica conditional edges per utilizzare intelligent routing
   graph.add_conditional_edges(
       "health_check",
       intelligent_routing_node,
       {
           "execute_action": "act",
           "conservative_action": "conservative_act",
           "escalate_incident": "escalate", 
           "monitor_and_wait": "monitor",
           "evaluate": "evaluate"
       }
   )

2. Test the new routing:
   
   curl -X POST http://localhost:8010/agent/graph/run \
     -H "Content-Type: application/json" \
     -d '{
       "incident": {
         "severity": "critical",
         "incident_type": "database_failure"
       }
     }'

3. Monitor routing decisions nei logs per tuning.
"""

if __name__ == "__main__":
    test_routing_scenarios()