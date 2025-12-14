"""
Base Graph - Foundation for all LangGraph agents.
"""
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import operator


class AgentState(TypedDict):
    """
    State shared across all agent nodes.
    
    Attributes:
        messages: Conversation history
        tenant_id: Tenant for isolation
        agent_id: Current agent ID
        task_type: Type of task being performed
        tools_used: List of tools that were called
        iteration: Current iteration count
        output: Final output
        error: Error message if failed
        metadata: Additional context
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tenant_id: str
    agent_id: Optional[str]
    task_type: Optional[str]
    tools_used: List[str]
    iteration: int
    output: Optional[str]
    error: Optional[str]
    metadata: Dict[str, Any]


def create_base_graph(
    name: str = "base_agent",
) -> StateGraph:
    """
    Create a base graph with common structure.
    
    Args:
        name: Name of the graph
        
    Returns:
        StateGraph instance ready to be extended
    """
    graph = StateGraph(AgentState)
    
    # Add common entry point
    graph.add_node("initialize", initialize_node)
    graph.set_entry_point("initialize")
    
    return graph


def initialize_node(state: AgentState) -> Dict[str, Any]:
    """Initialize agent state with defaults."""
    return {
        "iteration": state.get("iteration", 0) + 1,
        "tools_used": state.get("tools_used", []),
        "metadata": state.get("metadata", {}),
    }


def should_continue(state: AgentState, max_iterations: int = 25) -> str:
    """
    Determine if agent should continue or end.
    
    Args:
        state: Current agent state
        max_iterations: Maximum allowed iterations
        
    Returns:
        "continue" or "end"
    """
    # Check iteration limit
    if state.get("iteration", 0) >= max_iterations:
        return "end"
    
    # Check for errors
    if state.get("error"):
        return "end"
    
    # Check if output is ready
    if state.get("output"):
        return "end"
    
    return "continue"


def format_messages_for_llm(
    messages: Sequence[BaseMessage],
    system_prompt: str = None,
    max_messages: int = 20,
) -> List[BaseMessage]:
    """
    Format messages for LLM input.
    
    Args:
        messages: Raw message history
        system_prompt: Optional system prompt to prepend
        max_messages: Maximum messages to include
        
    Returns:
        Formatted message list
    """
    formatted = []
    
    # Add system prompt if provided
    if system_prompt:
        formatted.append(SystemMessage(content=system_prompt))
    
    # Take last N messages
    recent = list(messages)[-max_messages:]
    formatted.extend(recent)
    
    return formatted


def create_error_response(error: str, state: AgentState) -> Dict[str, Any]:
    """Create standardized error response."""
    return {
        "error": error,
        "output": f"Désolé, une erreur s'est produite: {error}",
        "messages": state.get("messages", []) + [
            AIMessage(content=f"❌ Erreur: {error}")
        ],
    }
