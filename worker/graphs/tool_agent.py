"""
Tool Agent Graph - Agent with MCP tool calling capabilities.
"""
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import structlog

from config import settings
from graphs.base import AgentState, initialize_node, should_continue, create_error_response

logger = structlog.get_logger()


async def create_tool_agent_graph(
    agent_id: str,
    tenant_id: str,
    tools: List[Any] = None,
) -> StateGraph:
    """
    Create a tool-calling agent graph.
    
    Args:
        agent_id: Agent ID for configuration
        tenant_id: Tenant ID for isolation
        tools: List of LangChain tools to use
        
    Returns:
        Compiled LangGraph
    """
    from tools import get_tools_for_agent
    
    # Load agent configuration and tools
    agent_config = await load_agent_config(agent_id, tenant_id)
    
    if tools is None:
        tools = await get_tools_for_agent(agent_id, tenant_id)
    
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("agent", create_agent_node(agent_config, tools))
    graph.add_node("tools", ToolNode(tools) if tools else passthrough_node)
    graph.add_node("finalize", finalize_node)
    
    # Set entry point
    graph.set_entry_point("initialize")
    
    # Add edges
    graph.add_edge("initialize", "agent")
    graph.add_conditional_edges(
        "agent",
        should_use_tools,
        {
            "tools": "tools",
            "finalize": "finalize",
            "error": "finalize",
        }
    )
    graph.add_edge("tools", "agent")  # After tools, go back to agent
    graph.add_edge("finalize", END)
    
    return graph.compile()


async def load_agent_config(agent_id: str, tenant_id: str) -> Dict[str, Any]:
    """Load agent configuration from database."""
    # TODO: Load from database
    return {
        "id": agent_id,
        "name": "Agent",
        "system_prompt": "Tu es un assistant IA helpful.",
        "max_iterations": settings.MAX_ITERATIONS,
    }


def create_agent_node(agent_config: Dict[str, Any], tools: List[Any]):
    """Create the main agent reasoning node."""
    
    async def agent_node(state: AgentState) -> Dict[str, Any]:
        """Main agent reasoning step."""
        from langchain_groq import ChatGroq
        from langchain_openai import ChatOpenAI
        
        # Get LLM based on tenant config
        # For now, use Groq (free)
        if settings.GROQ_API_KEY:
            llm = ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
            )
        elif settings.OPENAI_API_KEY:
            llm = ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                model="gpt-4o-mini",
                temperature=0.7,
            )
        else:
            return create_error_response("No LLM configured", state)
        
        # Bind tools if available
        if tools:
            llm = llm.bind_tools(tools)
        
        # Build messages
        messages = list(state.get("messages", []))
        
        # Add system prompt if first iteration
        if state.get("iteration", 0) <= 1 and agent_config.get("system_prompt"):
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=agent_config["system_prompt"])] + messages
        
        try:
            # Call LLM
            response = await llm.ainvoke(messages)
            
            logger.info(
                "Agent LLM call completed",
                agent_id=agent_config.get("id"),
                has_tool_calls=bool(response.tool_calls) if hasattr(response, 'tool_calls') else False,
            )
            
            return {
                "messages": [response],
                "iteration": state.get("iteration", 0) + 1,
            }
            
        except Exception as e:
            logger.error("Agent LLM call failed", error=str(e))
            return create_error_response(str(e), state)
    
    return agent_node


def should_use_tools(state: AgentState) -> str:
    """Determine if agent should use tools or finalize."""
    messages = state.get("messages", [])
    
    if not messages:
        return "finalize"
    
    last_message = messages[-1]
    
    # Check for errors
    if state.get("error"):
        return "error"
    
    # Check iteration limit
    if state.get("iteration", 0) >= settings.MAX_ITERATIONS:
        return "finalize"
    
    # Check if last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    return "finalize"


async def passthrough_node(state: AgentState) -> Dict[str, Any]:
    """Passthrough when no tools available."""
    return {}


def finalize_node(state: AgentState) -> Dict[str, Any]:
    """Finalize agent output."""
    messages = state.get("messages", [])
    
    # Get last AI message as output
    output = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            output = msg.content
            break
    
    # Collect tools used
    tools_used = state.get("tools_used", [])
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tools_used.append(msg.name)
    
    return {
        "output": output or "Aucune réponse générée.",
        "tools_used": list(set(tools_used)),
    }
