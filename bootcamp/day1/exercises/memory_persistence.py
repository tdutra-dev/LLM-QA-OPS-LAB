"""
Exercise 1.5: Memory & Persistence

Implementa checkpointing avanzato e memory management per LangGraph agents.
Focus su: state persistence, recovery da failures, versioning, e distributed memory.

OBIETTIVO: 
- Custom checkpointer con Redis/PostgreSQL
- State versioning e rollback capabilities  
- Distributed memory per multi-agent coordination
- Recovery strategies per failures
"""

import json
import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import redis
import asyncpg
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.checkpoint.base import CheckpointMetadata, Checkpoint

# ============================================================================
# Data Models per Advanced Memory
# ============================================================================

@dataclass
class StateSnapshot:
    """Immutable snapshot of agent state at a point in time"""
    
    checkpoint_id: str
    timestamp: float
    state: Dict[str, Any]
    metadata: Dict[str, Any]
    version: int
    parent_checkpoint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        return cls(**data)
    
    def create_child(self, new_state: Dict[str, Any], new_metadata: Optional[Dict] = None) -> "StateSnapshot":
        """Create a child snapshot with incremented version"""
        return StateSnapshot(
            checkpoint_id=self._generate_checkpoint_id(new_state),
            timestamp=time.time(),
            state=new_state,
            metadata=new_metadata or {},
            version=self.version + 1,
            parent_checkpoint=self.checkpoint_id
        )
    
    @staticmethod
    def _generate_checkpoint_id(state: Dict[str, Any]) -> str:
        """Generate deterministic checkpoint ID based on state content"""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

@dataclass 
class MemoryContext:
    """Context per memory operations - what to remember across workflows"""
    
    agent_id: str
    thread_id: str
    session_id: Optional[str] = None
    workflow_type: str = "default"
    retention_policy: str = "persistent"  # persistent | session | temporary
    max_snapshots: int = 100

# ============================================================================
# TODO 1: Custom Redis Checkpointer
# ============================================================================

class RedisCheckpointer(BaseCheckpointSaver):
    """
    High-performance checkpointer using Redis per low-latency state storage.
    Ideal per agents che necessitano fast state access.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = "langgraph:checkpoint"
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Load checkpoint from Redis"""
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return None
                
            key = f"{self.key_prefix}:{thread_id}"
            data = self.redis.get(key)
            
            if not data:
                return None
                
            checkpoint_data = json.loads(data)
            return self._deserialize_checkpoint(checkpoint_data)
            
        except Exception as e:
            print(f"Error loading checkpoint from Redis: {e}")
            return None
    
    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> None:
        """Save checkpoint to Redis"""
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return
                
            key = f"{self.key_prefix}:{thread_id}"
            
            # Serialize checkpoint with metadata
            checkpoint_data = self._serialize_checkpoint(checkpoint, metadata)
            
            # Save with TTL (24 hours default)
            ttl = 60 * 60 * 24  # 24 hours
            self.redis.setex(key, ttl, json.dumps(checkpoint_data))
            
            # Also save to history with versioning
            self._save_to_history(thread_id, checkpoint_data)
            
        except Exception as e:
            print(f"Error saving checkpoint to Redis: {e}")
    
    def list(self, config: Dict[str, Any]) -> List[CheckpointMetadata]:
        """List all checkpoints per a thread"""
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return []
                
            pattern = f"{self.key_prefix}:history:{thread_id}:*"
            keys = self.redis.keys(pattern)
            
            metadata_list = []
            for key in sorted(keys):
                data = self.redis.get(key)
                if data:
                    checkpoint_data = json.loads(data)
                    metadata = checkpoint_data.get("metadata", {})
                    metadata_list.append(metadata)
            
            return metadata_list
            
        except Exception as e:
            print(f"Error listing checkpoints: {e}")
            return []
    
    def _save_to_history(self, thread_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Save checkpoint to versioned history"""
        timestamp = int(time.time() * 1000)  # milliseconds
        history_key = f"{self.key_prefix}:history:{thread_id}:{timestamp}"
        
        # Save with longer TTL for history
        ttl = 60 * 60 * 24 * 7  # 7 days
        self.redis.setex(history_key, ttl, json.dumps(checkpoint_data))
    
    def _serialize_checkpoint(self, checkpoint: Checkpoint, metadata: CheckpointMetadata) -> Dict[str, Any]:
        """Convert checkpoint to serializable format"""
        return {
            "checkpoint": {
                "v": checkpoint.get("v", 1),
                "ts": checkpoint.get("ts"),
                "id": checkpoint.get("id"),
                "channel_values": checkpoint.get("channel_values", {}),
                "channel_versions": checkpoint.get("channel_versions", {}),
                "versions_seen": checkpoint.get("versions_seen", {})
            },
            "metadata": metadata or {},
            "saved_at": time.time()
        }
    
    def _deserialize_checkpoint(self, data: Dict[str, Any]) -> Checkpoint:
        """Convert serialized data back to checkpoint"""
        checkpoint_data = data.get("checkpoint", {})
        return Checkpoint(
            v=checkpoint_data.get("v", 1),
            ts=checkpoint_data.get("ts"),
            id=checkpoint_data.get("id"),
            channel_values=checkpoint_data.get("channel_values", {}),
            channel_versions=checkpoint_data.get("channel_versions", {}),
            versions_seen=checkpoint_data.get("versions_seen", {})
        )

# ============================================================================
# TODO 2: PostgreSQL Persistent Checkpointer  
# ============================================================================

class PostgreSQLCheckpointer(BaseCheckpointSaver):
    """
    Durable checkpointer using PostgreSQL per long-term state persistence.
    Include advanced features like state versioning e recovery.
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection pool e create tables"""
        self.pool = await asyncpg.create_pool(self.database_url)
        await self._create_tables()
    
    async def _create_tables(self):
        """Create necessary tables for checkpointing"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
                    id SERIAL PRIMARY KEY,
                    thread_id VARCHAR(255) NOT NULL,
                    checkpoint_id VARCHAR(255) NOT NULL,
                    checkpoint_data JSONB NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}',
                    version INTEGER NOT NULL DEFAULT 1,
                    parent_checkpoint_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    UNIQUE(thread_id, checkpoint_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
                ON langgraph_checkpoints(thread_id);
                
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
                ON langgraph_checkpoints(created_at);
            """)
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Get latest checkpoint for thread"""
        return asyncio.run(self._async_get(config))
    
    async def _async_get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Async version of get"""
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id or not self.pool:
                return None
                
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT checkpoint_data 
                    FROM langgraph_checkpoints 
                    WHERE thread_id = $1 
                    ORDER BY version DESC, created_at DESC 
                    LIMIT 1
                """, thread_id)
                
                if not row:
                    return None
                
                return self._deserialize_checkpoint(row["checkpoint_data"])
                
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return None
    
    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> None:
        """Save checkpoint"""
        asyncio.run(self._async_put(config, checkpoint, metadata))
    
    async def _async_put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata):
        """Async version of put"""
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id or not self.pool:
                return
                
            checkpoint_id = self._generate_checkpoint_id(checkpoint)
            checkpoint_data = self._serialize_checkpoint(checkpoint)
            
            async with self.pool.acquire() as conn:
                # Get current version
                current_version = await conn.fetchval("""
                    SELECT COALESCE(MAX(version), 0) + 1 
                    FROM langgraph_checkpoints 
                    WHERE thread_id = $1
                """, thread_id)
                
                # Insert new checkpoint
                await conn.execute("""
                    INSERT INTO langgraph_checkpoints 
                    (thread_id, checkpoint_id, checkpoint_data, metadata, version)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (thread_id, checkpoint_id) 
                    DO UPDATE SET 
                        checkpoint_data = EXCLUDED.checkpoint_data,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                """, thread_id, checkpoint_id, checkpoint_data, metadata or {}, current_version)
                
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    async def get_checkpoint_history(self, thread_id: str, limit: int = 10) -> List[StateSnapshot]:
        """Get checkpoint history for a thread"""
        if not self.pool:
            return []
            
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT checkpoint_id, checkpoint_data, metadata, version, created_at
                FROM langgraph_checkpoints 
                WHERE thread_id = $1 
                ORDER BY version DESC, created_at DESC 
                LIMIT $2
            """, thread_id, limit)
            
            snapshots = []
            for row in rows:
                snapshot = StateSnapshot(
                    checkpoint_id=row["checkpoint_id"],
                    timestamp=row["created_at"].timestamp(),
                    state=row["checkpoint_data"]["channel_values"],
                    metadata=row["metadata"],
                    version=row["version"]
                )
                snapshots.append(snapshot)
            
            return snapshots
    
    async def rollback_to_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """Rollback to a specific checkpoint"""
        if not self.pool:
            return False
            
        async with self.pool.acquire() as conn:
            # Get the target checkpoint
            row = await conn.fetchrow("""
                SELECT checkpoint_data, version 
                FROM langgraph_checkpoints 
                WHERE thread_id = $1 AND checkpoint_id = $2
            """, thread_id, checkpoint_id)
            
            if not row:
                return False
            
            # Create new checkpoint with rollback marker
            new_version = await conn.fetchval("""
                SELECT COALESCE(MAX(version), 0) + 1 
                FROM langgraph_checkpoints 
                WHERE thread_id = $1
            """, thread_id)
            
            rollback_id = f"rollback_{int(time.time())}"
            metadata = {
                "rollback": True, 
                "rolled_back_from": checkpoint_id,
                "original_version": row["version"]
            }
            
            await conn.execute("""
                INSERT INTO langgraph_checkpoints 
                (thread_id, checkpoint_id, checkpoint_data, metadata, version)
                VALUES ($1, $2, $3, $4, $5)
            """, thread_id, rollback_id, row["checkpoint_data"], metadata, new_version)
            
            return True
    
    def _generate_checkpoint_id(self, checkpoint: Checkpoint) -> str:
        """Generate unique checkpoint ID"""
        content = json.dumps(checkpoint.get("channel_values", {}), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> Dict[str, Any]:
        """Serialize checkpoint for storage"""
        return {
            "v": checkpoint.get("v", 1),
            "ts": checkpoint.get("ts"),
            "id": checkpoint.get("id"),
            "channel_values": checkpoint.get("channel_values", {}),
            "channel_versions": checkpoint.get("channel_versions", {}),
            "versions_seen": checkpoint.get("versions_seen", {})
        }
    
    def _deserialize_checkpoint(self, data: Dict[str, Any]) -> Checkpoint:
        """Deserialize checkpoint from storage"""
        return Checkpoint(
            v=data.get("v", 1),
            ts=data.get("ts"),
            id=data.get("id"),
            channel_values=data.get("channel_values", {}),
            channel_versions=data.get("channel_versions", {}),
            versions_seen=data.get("versions_seen", {})
        )

# ============================================================================
# TODO 3: Memory Manager per Multi-Agent Coordination
# ============================================================================

class DistributedMemoryManager:
    """
    Manage shared memory across multiple agents per coordination.
    Supports: shared state, message passing, coordination primitives.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.shared_state_prefix = "shared_state"
        self.message_queue_prefix = "agent_messages"
    
    async def set_shared_state(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None):
        """Set shared state accessible by all agents"""
        full_key = f"{self.shared_state_prefix}:{key}"
        serialized_value = json.dumps(value)
        
        if ttl:
            self.redis.setex(full_key, ttl, serialized_value)
        else:
            self.redis.set(full_key, serialized_value)
    
    async def get_shared_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Get shared state"""
        full_key = f"{self.shared_state_prefix}:{key}"
        data = self.redis.get(full_key)
        
        if data:
            return json.loads(data)
        return None
    
    async def send_agent_message(self, from_agent: str, to_agent: str, message: Dict[str, Any]):
        """Send message between agents"""
        queue_key = f"{self.message_queue_prefix}:{to_agent}"
        envelope = {
            "from": from_agent,
            "to": to_agent,
            "timestamp": time.time(),
            "message": message
        }
        
        self.redis.lpush(queue_key, json.dumps(envelope))
    
    async def receive_agent_messages(self, agent_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Receive messages for an agent"""
        queue_key = f"{self.message_queue_prefix}:{agent_id}"
        
        messages = []
        for _ in range(max_messages):
            data = self.redis.rpop(queue_key)
            if not data:
                break
            messages.append(json.loads(data))
        
        return messages
    
    async def coordinate_action(self, coordination_key: str, agent_id: str, action: str) -> bool:
        """
        Coordinate action across multiple agents using distributed locking.
        Returns True if this agent should proceed with the action.
        """
        lock_key = f"coordination_lock:{coordination_key}"
        
        # Try to acquire lock
        acquired = self.redis.set(lock_key, agent_id, nx=True, ex=30)  # 30 second lock
        
        if acquired:
            # This agent acquired the lock
            return True
        else:
            # Another agent has the lock
            lock_holder = self.redis.get(lock_key)
            print(f"Agent {agent_id} waiting for {lock_holder} to complete {action}")
            return False

# ============================================================================
# TODO 4: Integration with LangGraph
# ============================================================================

class AdvancedMemoryConfig:
    """Configuration for advanced memory features"""
    
    @staticmethod
    def create_hybrid_checkpointer(redis_url: str, postgres_url: str):
        """
        Create a hybrid checkpointer che usa Redis per fast access
        e PostgreSQL per persistence.
        """
        # For demo purposes, return Redis checkpointer
        # In production, implement logic to write to both
        return RedisCheckpointer(redis_url)
    
    @staticmethod  
    def create_graph_with_advanced_memory(graph_factory, config: MemoryContext):
        """Create LangGraph with advanced memory configuration"""
        
        # Choose checkpointer based on retention policy
        if config.retention_policy == "temporary":
            # In-memory checkpointer
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
        elif config.retention_policy == "session":
            # Redis checkpointer
            checkpointer = RedisCheckpointer()
        else:
            # PostgreSQL for persistent storage
            checkpointer = PostgreSQLCheckpointer("postgresql://localhost/langgraph")
        
        # Create graph with checkpointer
        graph = graph_factory()
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        return compiled_graph

# ============================================================================
# TODO 5: Testing e Examples
# ============================================================================

async def test_memory_systems():
    """Test the memory and persistence systems"""
    
    print("Testing Redis Checkpointer...")
    redis_checkpointer = RedisCheckpointer()
    
    # Test basic checkpoint operations
    test_config = {"configurable": {"thread_id": "test_thread_1"}}
    
    print("\\nTesting Distributed Memory Manager...")
    memory_manager = DistributedMemoryManager()
    
    # Test shared state
    await memory_manager.set_shared_state("system_status", {
        "health": "healthy",
        "load": 0.65,
        "active_agents": ["agent1", "agent2"]
    })
    
    status = await memory_manager.get_shared_state("system_status")
    print(f"Shared state: {status}")
    
    # Test agent messaging
    await memory_manager.send_agent_message("agent1", "agent2", {
        "type": "coordination_request",
        "action": "restart_database"
    })
    
    messages = await memory_manager.receive_agent_messages("agent2")
    print(f"Agent2 received messages: {messages}")

# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
Per integrare advanced memory nel tuo LangGraph:

1. Replace default checkpointer in langgraph_agent.py:

    from bootcamp.day1.exercises.memory_persistence import RedisCheckpointer
    
    # In create_compiled_graph()
    checkpointer = RedisCheckpointer()
    compiled = graph.compile(checkpointer=checkpointer)

2. Add memory context to your agent state:

    class AgentState(TypedDict):
        # ... existing fields ...
        memory_context: MemoryContext
        shared_state_keys: List[str]

3. Add memory management node:

    async def manage_memory_node(state: AgentState) -> AgentState:
        # Update shared state, send messages, coordinate actions
        return state

4. Test with rollback capability:

    # In case of errors, rollback to previous state
    POST /agent/rollback/{thread_id}/{checkpoint_id}

5. Monitor memory usage:

    # Add Prometheus metrics for memory operations
    checkpoint_size = len(json.dumps(state))
    memory_usage_bytes.observe(checkpoint_size)
"""

if __name__ == "__main__":
    asyncio.run(test_memory_systems())