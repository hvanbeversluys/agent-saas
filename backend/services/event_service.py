"""
Event Service - Server-Sent Events (SSE) pour les notifications temps réel.
Utilise Redis Pub/Sub pour la communication inter-services.
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional, Set
from datetime import datetime
import redis.asyncio as aioredis
import structlog

from config import settings

logger = structlog.get_logger()


class EventService:
    """Service pour gérer les événements temps réel via SSE + Redis Pub/Sub."""
    
    # Types d'événements supportés
    EVENT_TYPES = {
        "workflow.started",
        "workflow.step_completed", 
        "workflow.completed",
        "workflow.failed",
        "agent.response",
        "agent.tool_called",
        "agent.thinking",
        "chat.message",
        "notification.info",
        "notification.success",
        "notification.error",
    }
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        # Active SSE connections per tenant
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
    
    async def get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def close(self):
        """Close Redis connections."""
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
    
    # === Publishing Events ===
    
    async def publish(
        self,
        event_type: str,
        tenant_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """
        Publie un événement sur le channel Redis du tenant.
        
        Args:
            event_type: Type d'événement (workflow.completed, chat.message, etc.)
            tenant_id: ID du tenant pour le routing
            data: Données de l'événement
            user_id: ID utilisateur spécifique (optionnel)
        """
        event = {
            "type": event_type,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        channel = f"events:{tenant_id}"
        
        try:
            redis = await self.get_redis()
            await redis.publish(channel, json.dumps(event))
            
            logger.debug(
                "event_published",
                event_type=event_type,
                tenant_id=tenant_id,
                channel=channel
            )
        except Exception as e:
            logger.error("event_publish_failed", error=str(e))
    
    async def publish_workflow_event(
        self,
        tenant_id: str,
        workflow_id: str,
        execution_id: str,
        event_type: str,
        data: Dict[str, Any] = None
    ):
        """Helper pour publier un événement workflow."""
        await self.publish(
            event_type=f"workflow.{event_type}",
            tenant_id=tenant_id,
            data={
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                **(data or {})
            }
        )
    
    async def publish_chat_event(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        event_type: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Helper pour publier un événement chat."""
        await self.publish(
            event_type=f"agent.{event_type}",
            tenant_id=tenant_id,
            user_id=user_id,
            data={
                "conversation_id": conversation_id,
                "content": content,
                **(metadata or {})
            }
        )
    
    # === SSE Subscription ===
    
    async def subscribe(
        self,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Générateur SSE pour un tenant/user.
        Yield les événements au format SSE.
        
        Usage:
            async for event in event_service.subscribe(tenant_id):
                yield event
        """
        channel = f"events:{tenant_id}"
        queue: asyncio.Queue = asyncio.Queue()
        
        # Register connection
        if tenant_id not in self._connections:
            self._connections[tenant_id] = set()
        self._connections[tenant_id].add(queue)
        
        logger.info("sse_client_connected", tenant_id=tenant_id, user_id=user_id)
        
        # Send initial connection event
        yield self._format_sse({
            "type": "connected",
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        try:
            redis = await self.get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
            
            # Listen for messages
            async for message in pubsub.listen():
                if message["type"] == "message":
                    event_data = json.loads(message["data"])
                    
                    # Filter by user if specified
                    if user_id and event_data.get("user_id"):
                        if event_data["user_id"] != user_id:
                            continue
                    
                    yield self._format_sse(event_data)
                    
        except asyncio.CancelledError:
            logger.info("sse_client_disconnected", tenant_id=tenant_id)
        finally:
            # Cleanup
            if tenant_id in self._connections:
                self._connections[tenant_id].discard(queue)
            await pubsub.unsubscribe(channel)
    
    def _format_sse(self, data: Dict[str, Any]) -> str:
        """Format data as SSE event."""
        event_type = data.get("type", "message")
        json_data = json.dumps(data)
        return f"event: {event_type}\ndata: {json_data}\n\n"
    
    # === Local Broadcasting (without Redis) ===
    
    async def broadcast_local(
        self,
        tenant_id: str,
        event: Dict[str, Any]
    ):
        """Broadcast to local connections (same process)."""
        if tenant_id in self._connections:
            for queue in self._connections[tenant_id]:
                await queue.put(event)
    
    def get_connection_count(self, tenant_id: str = None) -> int:
        """Get number of active SSE connections."""
        if tenant_id:
            return len(self._connections.get(tenant_id, set()))
        return sum(len(conns) for conns in self._connections.values())


# Singleton
_event_service: Optional[EventService] = None


def get_event_service() -> EventService:
    """Get or create EventService singleton."""
    global _event_service
    if _event_service is None:
        _event_service = EventService()
    return _event_service
