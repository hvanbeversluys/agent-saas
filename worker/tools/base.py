"""
Base Tool - Abstract base class for all MCP tools.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from langchain_core.tools import BaseTool as LangChainBaseTool
import structlog

logger = structlog.get_logger()


class ToolInput(BaseModel):
    """Base input schema for tools."""
    pass


class BaseTool(ABC):
    """
    Abstract base class for MCP tools.
    
    All tools must implement:
    - name: Tool identifier
    - description: Human-readable description
    - args_schema: Pydantic model for inputs
    - _execute: Actual execution logic
    """
    
    name: str = "base_tool"
    description: str = "Base tool description"
    args_schema: Type[BaseModel] = ToolInput
    
    def __init__(self, tenant_id: str, config: Dict[str, Any] = None):
        """
        Initialize tool with tenant context.
        
        Args:
            tenant_id: Tenant ID for credential lookup
            config: Optional tool configuration
        """
        self.tenant_id = tenant_id
        self.config = config or {}
    
    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """Execute the tool. Must be implemented by subclasses."""
        pass
    
    async def run(self, **kwargs) -> Any:
        """
        Run the tool with logging and error handling.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.info(
            "Tool execution started",
            tool=self.name,
            tenant_id=self.tenant_id,
        )
        
        try:
            result = await self._execute(**kwargs)
            
            logger.info(
                "Tool execution completed",
                tool=self.name,
                success=True,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Tool execution failed",
                tool=self.name,
                error=str(e),
            )
            raise
    
    def to_langchain_tool(self) -> LangChainBaseTool:
        """Convert to LangChain tool for use in agents."""
        from langchain_core.tools import StructuredTool
        
        return StructuredTool.from_function(
            func=self._sync_wrapper,
            coroutine=self._execute,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )
    
    def _sync_wrapper(self, **kwargs) -> Any:
        """Sync wrapper for async execute."""
        import asyncio
        return asyncio.run(self._execute(**kwargs))
    
    async def validate_credentials(self) -> bool:
        """Validate that required credentials are configured."""
        return True
    
    def get_required_config(self) -> list:
        """Return list of required configuration keys."""
        return []
