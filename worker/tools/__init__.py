"""
Tools module - MCP tool implementations.
"""
from typing import List, Any
from tools.base import BaseTool
from tools.email import EmailTool
from tools.calendar import CalendarTool
from tools.crm import CRMTool

# Tool registry
AVAILABLE_TOOLS = {
    "email": EmailTool,
    "calendar": CalendarTool,
    "crm": CRMTool,
}


async def get_tools_for_agent(agent_id: str, tenant_id: str) -> List[Any]:
    """
    Load tools configured for an agent.
    
    Args:
        agent_id: Agent ID
        tenant_id: Tenant ID for credential lookup
        
    Returns:
        List of LangChain tools
    """
    # TODO: Load from database based on agent config
    # For now, return empty list
    return []


def get_tool_by_id(tool_id: str, tenant_id: str) -> BaseTool:
    """Get a specific tool by ID."""
    tool_class = AVAILABLE_TOOLS.get(tool_id)
    if not tool_class:
        raise ValueError(f"Unknown tool: {tool_id}")
    return tool_class(tenant_id=tenant_id)


__all__ = [
    "BaseTool",
    "EmailTool", 
    "CalendarTool",
    "CRMTool",
    "get_tools_for_agent",
    "get_tool_by_id",
    "AVAILABLE_TOOLS",
]
