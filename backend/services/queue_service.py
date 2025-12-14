"""
Queue Service - Intégration Redis pour les tâches async.
Envoie des jobs au worker LangGraph via Redis.
"""
import json
import redis
from typing import Any, Dict, Optional
from datetime import datetime
import structlog

from config import settings

logger = structlog.get_logger()


class QueueService:
    """Service pour envoyer des tâches au worker via Redis."""
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._client: Optional[redis.Redis] = None
    
    @property
    def client(self) -> redis.Redis:
        """Connexion Redis lazy-loaded."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True
            )
        return self._client
    
    def is_available(self) -> bool:
        """Vérifie si Redis est disponible."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.warning("redis_unavailable", error=str(e))
            return False
    
    def enqueue_workflow(
        self,
        execution_id: str,
        workflow_id: str,
        tenant_id: str,
        input_data: Dict[str, Any],
        priority: str = "normal"
    ) -> bool:
        """
        Enqueue un workflow pour exécution par le worker.
        
        Args:
            execution_id: ID de l'exécution créée
            workflow_id: ID du workflow à exécuter
            tenant_id: ID du tenant pour isolation
            input_data: Données d'entrée du workflow
            priority: "high", "normal", "low"
        
        Returns:
            True si enqueued avec succès
        """
        job = {
            "task": "execute_workflow",
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "tenant_id": tenant_id,
            "input_data": input_data,
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat()
        }
        
        try:
            # ARQ utilise le format arq:queue:default
            queue_name = f"arq:queue:{priority}" if priority != "normal" else "arq:queue:default"
            
            # Format ARQ: job serialisé en JSON
            self.client.rpush(queue_name, json.dumps(job))
            
            logger.info(
                "workflow_enqueued",
                execution_id=execution_id,
                workflow_id=workflow_id,
                queue=queue_name
            )
            return True
            
        except Exception as e:
            logger.error(
                "workflow_enqueue_failed",
                execution_id=execution_id,
                error=str(e)
            )
            return False
    
    def enqueue_agent_task(
        self,
        task_type: str,
        agent_id: str,
        tenant_id: str,
        payload: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Enqueue une tâche agent (chat async, tool call, etc).
        
        Returns:
            Job ID si enqueued, None sinon
        """
        import uuid
        job_id = str(uuid.uuid4())
        
        job = {
            "task": task_type,
            "job_id": job_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "payload": payload,
            "callback_url": callback_url,
            "enqueued_at": datetime.utcnow().isoformat()
        }
        
        try:
            self.client.rpush("arq:queue:default", json.dumps(job))
            logger.info("agent_task_enqueued", job_id=job_id, task_type=task_type)
            return job_id
        except Exception as e:
            logger.error("agent_task_enqueue_failed", error=str(e))
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Récupère le statut d'un job."""
        try:
            status = self.client.hget("arq:job:status", job_id)
            if status:
                return json.loads(status)
            return None
        except Exception:
            return None
    
    def publish_event(self, channel: str, event: Dict[str, Any]) -> bool:
        """Publie un événement sur un channel Redis (pub/sub)."""
        try:
            self.client.publish(channel, json.dumps(event))
            return True
        except Exception as e:
            logger.error("event_publish_failed", channel=channel, error=str(e))
            return False


# Instance singleton
queue_service = QueueService()


def get_queue_service() -> QueueService:
    """Dependency injection pour FastAPI."""
    return queue_service
