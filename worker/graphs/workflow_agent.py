"""
Workflow Agent Graph - Executes multi-step workflows.
"""
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage
import structlog
import operator

from config import settings

logger = structlog.get_logger()


class WorkflowState(TypedDict):
    """State for workflow execution."""
    workflow_id: str
    tenant_id: str
    current_step: int
    total_steps: int
    steps: List[Dict[str, Any]]
    step_results: Annotated[List[Dict[str, Any]], operator.add]
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    status: str  # pending, running, paused, completed, failed
    error: Optional[str]


async def create_workflow_agent_graph(
    workflow_id: str,
    tenant_id: str,
) -> StateGraph:
    """
    Create a workflow execution graph.
    
    Args:
        workflow_id: Workflow ID to execute
        tenant_id: Tenant ID for isolation
        
    Returns:
        Compiled LangGraph for workflow execution
    """
    # Load workflow definition
    workflow = await load_workflow(workflow_id, tenant_id)
    
    # Create graph
    graph = StateGraph(WorkflowState)
    
    # Add nodes
    graph.add_node("initialize", initialize_workflow)
    graph.add_node("execute_step", execute_workflow_step)
    graph.add_node("check_condition", check_step_condition)
    graph.add_node("handle_error", handle_workflow_error)
    graph.add_node("finalize", finalize_workflow)
    
    # Set entry point
    graph.set_entry_point("initialize")
    
    # Add edges
    graph.add_edge("initialize", "execute_step")
    graph.add_conditional_edges(
        "execute_step",
        route_after_step,
        {
            "next_step": "check_condition",
            "error": "handle_error",
            "complete": "finalize",
        }
    )
    graph.add_conditional_edges(
        "check_condition",
        route_after_condition,
        {
            "continue": "execute_step",
            "skip": "execute_step",
            "complete": "finalize",
        }
    )
    graph.add_edge("handle_error", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


async def load_workflow(workflow_id: str, tenant_id: str) -> Dict[str, Any]:
    """Load workflow definition from database."""
    # TODO: Load from database via backend API
    return {
        "id": workflow_id,
        "name": "Sample Workflow",
        "steps": [],
    }


def initialize_workflow(state: WorkflowState) -> Dict[str, Any]:
    """Initialize workflow execution state."""
    logger.info(
        "Initializing workflow",
        workflow_id=state.get("workflow_id"),
        tenant_id=state.get("tenant_id"),
    )
    
    return {
        "current_step": 0,
        "status": "running",
        "step_results": [],
        "output_data": {},
    }


async def execute_workflow_step(state: WorkflowState) -> Dict[str, Any]:
    """Execute current workflow step."""
    steps = state.get("steps", [])
    current_step = state.get("current_step", 0)
    
    if current_step >= len(steps):
        return {"status": "completed"}
    
    step = steps[current_step]
    step_type = step.get("type")
    
    logger.info(
        "Executing workflow step",
        workflow_id=state.get("workflow_id"),
        step_index=current_step,
        step_type=step_type,
    )
    
    try:
        result = await execute_step_by_type(step, state)
        
        return {
            "step_results": [{
                "step_index": current_step,
                "step_type": step_type,
                "status": "success",
                "output": result,
            }],
            "current_step": current_step + 1,
        }
        
    except Exception as e:
        logger.error(
            "Workflow step failed",
            step_index=current_step,
            error=str(e),
        )
        return {
            "step_results": [{
                "step_index": current_step,
                "step_type": step_type,
                "status": "failed",
                "error": str(e),
            }],
            "status": "failed",
            "error": str(e),
        }


async def execute_step_by_type(step: Dict[str, Any], state: WorkflowState) -> Any:
    """Execute a step based on its type."""
    step_type = step.get("type")
    config = step.get("config", {})
    
    if step_type == "llm_generate":
        return await execute_llm_step(config, state)
    
    elif step_type == "tool_call":
        return await execute_tool_step(config, state)
    
    elif step_type == "condition":
        return await execute_condition_step(config, state)
    
    elif step_type == "wait":
        return await execute_wait_step(config, state)
    
    elif step_type == "human_approval":
        return await execute_human_approval_step(config, state)
    
    else:
        raise ValueError(f"Unknown step type: {step_type}")


async def execute_llm_step(config: Dict[str, Any], state: WorkflowState) -> str:
    """Execute an LLM generation step."""
    from langchain_groq import ChatGroq
    
    prompt = config.get("prompt", "")
    
    # Replace variables in prompt
    input_data = state.get("input_data", {})
    for key, value in input_data.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))
    
    # Also use previous step outputs
    for result in state.get("step_results", []):
        if result.get("status") == "success":
            prompt = prompt.replace(
                f"{{step_{result['step_index']}_output}}",
                str(result.get("output", ""))
            )
    
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
    )
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return response.content


async def execute_tool_step(config: Dict[str, Any], state: WorkflowState) -> Any:
    """Execute a tool/action step."""
    tool_id = config.get("tool_id")
    tool_input = config.get("input", {})
    
    # TODO: Load and execute tool
    logger.info("Executing tool", tool_id=tool_id)
    
    return {"tool_id": tool_id, "status": "executed"}


async def execute_condition_step(config: Dict[str, Any], state: WorkflowState) -> bool:
    """Evaluate a condition step."""
    condition = config.get("condition", "true")
    
    # TODO: Evaluate condition against state
    return True


async def execute_wait_step(config: Dict[str, Any], state: WorkflowState) -> Dict:
    """Execute a wait/delay step."""
    import asyncio
    
    duration = config.get("duration_seconds", 1)
    await asyncio.sleep(min(duration, 60))  # Max 60s wait
    
    return {"waited": duration}


async def execute_human_approval_step(config: Dict[str, Any], state: WorkflowState) -> Dict:
    """Request human approval (pauses workflow)."""
    # TODO: Notify user and pause workflow
    return {
        "requires_approval": True,
        "message": config.get("message", "Approval required"),
    }


def route_after_step(state: WorkflowState) -> str:
    """Route after step execution."""
    if state.get("status") == "failed":
        return "error"
    
    if state.get("status") == "completed":
        return "complete"
    
    current_step = state.get("current_step", 0)
    total_steps = len(state.get("steps", []))
    
    if current_step >= total_steps:
        return "complete"
    
    return "next_step"


def route_after_condition(state: WorkflowState) -> str:
    """Route after condition check."""
    steps = state.get("steps", [])
    current_step = state.get("current_step", 0)
    
    if current_step >= len(steps):
        return "complete"
    
    return "continue"


def check_step_condition(state: WorkflowState) -> Dict[str, Any]:
    """Check if next step should be executed."""
    # TODO: Implement conditional logic
    return {}


def handle_workflow_error(state: WorkflowState) -> Dict[str, Any]:
    """Handle workflow execution error."""
    logger.error(
        "Workflow error",
        workflow_id=state.get("workflow_id"),
        error=state.get("error"),
    )
    return {"status": "failed"}


def finalize_workflow(state: WorkflowState) -> Dict[str, Any]:
    """Finalize workflow execution."""
    step_results = state.get("step_results", [])
    
    # Compile outputs
    output_data = {}
    for result in step_results:
        if result.get("status") == "success":
            output_data[f"step_{result['step_index']}"] = result.get("output")
    
    logger.info(
        "Workflow finalized",
        workflow_id=state.get("workflow_id"),
        status=state.get("status"),
        steps_completed=len([r for r in step_results if r.get("status") == "success"]),
    )
    
    return {
        "output_data": output_data,
        "status": state.get("status", "completed"),
    }
