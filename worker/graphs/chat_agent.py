"""
Chat Agent Graph - Conversational agent with memory.
"""
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import structlog

from config import settings
from graphs.base import AgentState, initialize_node

logger = structlog.get_logger()


async def create_chat_agent_graph(
    agent_id: str,
    tenant_id: str,
    system_prompt: str = None,
) -> StateGraph:
    """
    Create a simple chat agent graph.
    
    Args:
        agent_id: Agent ID
        tenant_id: Tenant ID
        system_prompt: Custom system prompt
        
    Returns:
        Compiled chat agent graph
    """
    # Load agent config if not provided
    if not system_prompt:
        config = await load_agent_config(agent_id, tenant_id)
        system_prompt = config.get("system_prompt", "Tu es un assistant IA helpful.")
    
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("generate", create_generate_node(system_prompt))
    graph.add_node("finalize", finalize_chat)
    
    # Set flow
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "generate")
    graph.add_edge("generate", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


async def load_agent_config(agent_id: str, tenant_id: str) -> Dict[str, Any]:
    """Load agent configuration."""
    # TODO: Load from database
    return {
        "id": agent_id,
        "name": "Chat Agent",
        "system_prompt": "Tu es un assistant IA professionnel et helpful.",
    }


def create_generate_node(system_prompt: str):
    """Create the generation node with system prompt."""
    
    async def generate_response(state: AgentState) -> Dict[str, Any]:
        """Generate chat response."""
        from langchain_groq import ChatGroq
        from langchain_openai import ChatOpenAI
        
        # Select LLM
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
            return {
                "error": "No LLM configured",
                "output": "Désolé, aucun modèle LLM n'est configuré.",
            }
        
        # Build messages
        messages = []
        
        # Add system prompt
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        # Add conversation history
        messages.extend(list(state.get("messages", [])))
        
        try:
            response = await llm.ainvoke(messages)
            
            logger.info(
                "Chat response generated",
                agent_id=state.get("agent_id"),
                response_length=len(response.content),
            )
            
            return {
                "messages": [response],
                "output": response.content,
            }
            
        except Exception as e:
            logger.error("Chat generation failed", error=str(e))
            return {
                "error": str(e),
                "output": f"Erreur lors de la génération: {str(e)}",
            }
    
    return generate_response


def finalize_chat(state: AgentState) -> Dict[str, Any]:
    """Finalize chat output."""
    return {
        "output": state.get("output"),
        "tools_used": [],
    }
