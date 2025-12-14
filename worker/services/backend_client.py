"""
Backend Client - Communication avec l'API Backend.
Permet au worker de récupérer les workflows et mettre à jour les statuts.
"""
import httpx
from typing import Any, Dict, List, Optional
import structlog

from config import settings

logger = structlog.get_logger()


class BackendClient:
    """Client HTTP pour communiquer avec le Backend API."""
    
    def __init__(self):
        self.base_url = settings.BACKEND_URL.rstrip("/")
        self.api_key = settings.BACKEND_API_KEY
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> Dict[str, str]:
        """Headers pour les requêtes API."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"agent-saas-worker/{settings.VERSION}"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def get_client(self) -> httpx.AsyncClient:
        """Lazy-load async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Ferme le client HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    # === Workflow Operations ===
    
    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un workflow par son ID."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/internal/workflows/{workflow_id}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning("workflow_not_found", workflow_id=workflow_id)
                return None
            else:
                logger.error(
                    "workflow_fetch_failed",
                    workflow_id=workflow_id,
                    status=response.status_code,
                    response=response.text
                )
                return None
                
        except httpx.RequestError as e:
            logger.error("workflow_fetch_error", workflow_id=workflow_id, error=str(e))
            return None
    
    async def get_workflow_tasks(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Récupère les tâches d'un workflow."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/internal/workflows/{workflow_id}/tasks")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error("workflow_tasks_fetch_failed", workflow_id=workflow_id)
                return []
                
        except httpx.RequestError as e:
            logger.error("workflow_tasks_fetch_error", error=str(e))
            return []
    
    # === Execution Updates ===
    
    async def update_execution_status(
        self,
        execution_id: str,
        status: str,
        current_task: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """Met à jour le statut d'une exécution."""
        payload = {
            "status": status,
            "current_task_order": current_task,
        }
        if output:
            payload["output_data"] = output
        if error:
            payload["error"] = error
        
        try:
            client = await self.get_client()
            response = await client.patch(
                f"/api/internal/executions/{execution_id}",
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(
                    "execution_status_updated",
                    execution_id=execution_id,
                    status=status
                )
                return True
            else:
                logger.error(
                    "execution_update_failed",
                    execution_id=execution_id,
                    status_code=response.status_code
                )
                return False
                
        except httpx.RequestError as e:
            logger.error("execution_update_error", error=str(e))
            return False
    
    async def complete_execution(
        self,
        execution_id: str,
        output: Dict[str, Any],
        success: bool = True
    ) -> bool:
        """Marque une exécution comme terminée."""
        status = "completed" if success else "failed"
        return await self.update_execution_status(
            execution_id=execution_id,
            status=status,
            output=output
        )
    
    async def fail_execution(
        self,
        execution_id: str,
        error: str
    ) -> bool:
        """Marque une exécution comme échouée."""
        return await self.update_execution_status(
            execution_id=execution_id,
            status="failed",
            error=error
        )
    
    # === Agent & Prompt Operations ===
    
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un agent par son ID."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/internal/agents/{agent_id}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning("agent_not_found", agent_id=agent_id)
                return None
                
        except httpx.RequestError as e:
            logger.error("agent_fetch_error", error=str(e))
            return None
    
    async def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un prompt par son ID."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/internal/prompts/{prompt_id}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError:
            return None
    
    # === Tenant LLM Config ===
    
    async def get_tenant_llm_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la configuration LLM d'un tenant."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/internal/tenants/{tenant_id}/llm-config")
            
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError as e:
            logger.error("llm_config_fetch_error", tenant_id=tenant_id, error=str(e))
            return None
    
    # === Health Check ===
    
    async def health_check(self) -> bool:
        """Vérifie que le backend est accessible."""
        try:
            client = await self.get_client()
            response = await client.get("/api/health")
            return response.status_code == 200
        except httpx.RequestError:
            return False


# Singleton instance
_backend_client: Optional[BackendClient] = None


def get_backend_client() -> BackendClient:
    """Get or create the backend client singleton."""
    global _backend_client
    if _backend_client is None:
        _backend_client = BackendClient()
    return _backend_client
