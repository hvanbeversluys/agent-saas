"""
Workflow Tasks - Async workflow execution tasks.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import structlog
from redis.asyncio import Redis

from config import settings

logger = structlog.get_logger()


async def run_workflow(
    workflow_id: str,
    tenant_id: str,
    input_data: Dict[str, Any],
    redis: Redis,
    execution_id: str = None,
) -> Dict[str, Any]:
    """
    Execute a complete workflow.
    
    Args:
        workflow_id: Workflow to execute
        tenant_id: Tenant ID
        input_data: Input data for workflow
        redis: Redis connection for state
        execution_id: Optional execution ID (auto-generated if not provided)
        
    Returns:
        Execution result with status and outputs
    """
    from graphs.workflow_agent import create_workflow_agent_graph
    import uuid
    
    execution_id = execution_id or str(uuid.uuid4())
    
    logger.info(
        "Starting workflow execution",
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        execution_id=execution_id,
    )
    
    # Store execution state in Redis
    state_key = f"workflow:{tenant_id}:{workflow_id}:{execution_id}"
    
    await redis.hset(state_key, mapping={
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
    })
    await redis.expire(state_key, 86400)  # 24h TTL
    
    try:
        # Load workflow definition
        workflow = await load_workflow_from_backend(workflow_id, tenant_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Create and execute graph
        graph = await create_workflow_agent_graph(workflow_id, tenant_id)
        
        result = await graph.ainvoke({
            "workflow_id": workflow_id,
            "tenant_id": tenant_id,
            "steps": workflow.get("tasks", []),
            "input_data": input_data,
            "current_step": 0,
            "total_steps": len(workflow.get("tasks", [])),
        })
        
        # Update execution state
        await redis.hset(state_key, mapping={
            "status": result.get("status", "completed"),
            "completed_at": datetime.utcnow().isoformat(),
            "steps_completed": len(result.get("step_results", [])),
        })
        
        # Notify backend of completion
        await notify_workflow_completed(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            result=result,
        )
        
        logger.info(
            "Workflow completed",
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=result.get("status"),
        )
        
        return {
            "execution_id": execution_id,
            "status": result.get("status", "completed"),
            "steps_completed": len(result.get("step_results", [])),
            "output_data": result.get("output_data", {}),
        }
        
    except Exception as e:
        logger.error(
            "Workflow failed",
            workflow_id=workflow_id,
            execution_id=execution_id,
            error=str(e),
        )
        
        # Update state
        await redis.hset(state_key, mapping={
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat(),
        })
        
        # Notify backend of failure
        await notify_workflow_failed(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            error=str(e),
        )
        
        return {
            "execution_id": execution_id,
            "status": "failed",
            "error": str(e),
        }


async def execute_workflow_step(
    workflow_id: str,
    tenant_id: str,
    step_index: int,
    step_config: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a single workflow step.
    
    Args:
        workflow_id: Parent workflow ID
        tenant_id: Tenant ID
        step_index: Step index in workflow
        step_config: Step configuration
        context: Execution context (previous outputs, etc.)
        
    Returns:
        Step result
    """
    step_type = step_config.get("type")
    
    logger.info(
        "Executing workflow step",
        workflow_id=workflow_id,
        step_index=step_index,
        step_type=step_type,
    )
    
    try:
        if step_type == "llm_generate":
            result = await execute_llm_step(step_config, context)
        elif step_type == "tool_call":
            result = await execute_tool_step(step_config, context, tenant_id)
        elif step_type == "condition":
            result = await execute_condition_step(step_config, context)
        elif step_type == "loop":
            result = await execute_loop_step(step_config, context, tenant_id)
        elif step_type == "human_approval":
            result = await execute_approval_step(step_config, context, tenant_id)
        else:
            raise ValueError(f"Unknown step type: {step_type}")
        
        return {
            "status": "success",
            "step_index": step_index,
            "step_type": step_type,
            "output": result,
        }
        
    except Exception as e:
        logger.error(
            "Step execution failed",
            step_index=step_index,
            error=str(e),
        )
        return {
            "status": "failed",
            "step_index": step_index,
            "step_type": step_type,
            "error": str(e),
        }


async def execute_llm_step(
    config: Dict[str, Any],
    context: Dict[str, Any],
    tenant_id: str = None,
) -> str:
    """Execute LLM generation step with tenant-specific config."""
    from langchain_core.messages import HumanMessage
    
    prompt = config.get("prompt", "")
    
    # Substitute variables
    for key, value in context.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))
    
    # Get tenant LLM config
    api_key, provider, model = await get_llm_for_tenant(tenant_id) if tenant_id else (
        settings.GROQ_API_KEY, "groq", "llama-3.3-70b-versatile"
    )
    
    # Override model if specified in config
    model = config.get("model", model)
    temperature = config.get("temperature", 0.7)
    
    # Create LLM based on provider
    if provider == "groq":
        from langchain_groq import ChatGroq
        llm = ChatGroq(api_key=api_key, model=model, temperature=temperature)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(api_key=api_key, model=model, temperature=temperature)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(api_key=api_key, model=model, temperature=temperature)
    else:
        # Fallback Groq
        from langchain_groq import ChatGroq
        llm = ChatGroq(api_key=api_key, model=model, temperature=temperature)
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return response.content


async def execute_tool_step(
    config: Dict[str, Any],
    context: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """Execute tool/action step."""
    from tools import get_tool_by_id
    
    tool_id = config.get("tool_id")
    tool_input = config.get("input", {})
    
    # Substitute variables in input
    for key, value in tool_input.items():
        if isinstance(value, str):
            for ctx_key, ctx_value in context.items():
                tool_input[key] = value.replace(f"{{{ctx_key}}}", str(ctx_value))
    
    tool = get_tool_by_id(tool_id, tenant_id)
    return await tool.run(**tool_input)


async def execute_condition_step(
    config: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate condition step."""
    condition = config.get("condition", "true")
    
    # Simple evaluation (TODO: safer evaluation)
    try:
        # Replace context variables
        for key, value in context.items():
            condition = condition.replace(f"{{{key}}}", repr(value))
        
        result = eval(condition)
        return {"condition_met": bool(result)}
    except Exception as e:
        logger.warning(f"Condition evaluation failed: {e}")
        return {"condition_met": True}


async def execute_loop_step(
    config: Dict[str, Any],
    context: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """Execute loop step."""
    items_key = config.get("items_key", "items")
    items = context.get(items_key, [])
    max_iterations = config.get("max_iterations", 100)
    
    results = []
    for i, item in enumerate(items[:max_iterations]):
        # TODO: Execute sub-steps for each item
        results.append({"index": i, "item": item})
    
    return {"iterations": len(results), "results": results}


async def execute_approval_step(
    config: Dict[str, Any],
    context: Dict[str, Any],
    tenant_id: str,
) -> Dict[str, Any]:
    """Request human approval (pauses workflow)."""
    message = config.get("message", "Approval required to continue")
    
    # TODO: Send notification to user
    # TODO: Pause workflow execution
    
    return {
        "requires_approval": True,
        "message": message,
        "status": "pending_approval",
    }


async def load_workflow_from_backend(
    workflow_id: str,
    tenant_id: str,
) -> Optional[Dict[str, Any]]:
    """Load workflow definition from backend API using BackendClient."""
    from services.backend_client import get_backend_client
    
    client = get_backend_client()
    
    try:
        # Get workflow
        workflow = await client.get_workflow(workflow_id)
        if not workflow:
            return None
        
        # Get tasks
        tasks = await client.get_workflow_tasks(workflow_id)
        workflow["tasks"] = tasks
        
        return workflow
        
    except Exception as e:
        logger.error("Failed to load workflow", error=str(e))
        return None


async def notify_workflow_completed(
    workflow_id: str,
    tenant_id: str,
    execution_id: str,
    result: Dict[str, Any],
):
    """Notify backend of workflow completion via BackendClient."""
    from services.backend_client import get_backend_client
    
    client = get_backend_client()
    
    await client.complete_execution(
        execution_id=execution_id,
        output=result.get("output_data", {}),
        success=True
    )


async def notify_workflow_failed(
    workflow_id: str,
    tenant_id: str,
    execution_id: str,
    error: str,
):
    """Notify backend of workflow failure via BackendClient."""
    from services.backend_client import get_backend_client
    
    client = get_backend_client()
    
    await client.fail_execution(
        execution_id=execution_id,
        error=error
    )


async def get_llm_for_tenant(tenant_id: str) -> tuple[str, str, str]:
    """
    Récupère la config LLM pour un tenant.
    
    Returns:
        (api_key, provider, model)
    """
    from services.backend_client import get_backend_client
    
    client = get_backend_client()
    config = await client.get_tenant_llm_config(tenant_id)
    
    if not config:
        # Fallback sur les settings du worker
        return (settings.GROQ_API_KEY, "groq", "llama-3.3-70b-versatile")
    
    usage_mode = config.get("usage_mode", "platform")
    byok_keys = config.get("byok_keys", {})
    
    # BYOK mode: utiliser les clés du tenant
    if usage_mode in ["byok", "hybrid"] and byok_keys:
        if byok_keys.get("groq"):
            return (byok_keys["groq"], "groq", "llama-3.3-70b-versatile")
        if byok_keys.get("openai"):
            return (byok_keys["openai"], "openai", "gpt-4o-mini")
        if byok_keys.get("anthropic"):
            return (byok_keys["anthropic"], "anthropic", "claude-3-haiku-20240307")
    
    # Platform mode: utiliser les clés de la plateforme
    if config.get("platform_groq_key"):
        return (config["platform_groq_key"], "groq", "llama-3.3-70b-versatile")
    if config.get("platform_openai_key"):
        return (config["platform_openai_key"], "openai", "gpt-4o-mini")
    
    # Ultimate fallback
    return (settings.GROQ_API_KEY, "groq", "llama-3.3-70b-versatile")
