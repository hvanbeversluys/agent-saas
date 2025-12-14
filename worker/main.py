"""
Worker Main - ARQ Worker with LangGraph integration.
"""
import asyncio
from typing import Any, Dict
from arq import cron, create_pool
from arq.connections import RedisSettings
import structlog

from config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ============================================================
# TASK DEFINITIONS
# ============================================================

async def execute_workflow(
    ctx: Dict[str, Any],
    workflow_id: str,
    tenant_id: str,
    trigger: str = "manual",
    input_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Execute a workflow using LangGraph.
    
    Args:
        ctx: ARQ context (contains redis connection)
        workflow_id: ID of the workflow to execute
        tenant_id: Tenant ID for isolation
        trigger: What triggered the workflow (manual, schedule, webhook)
        input_data: Input data for the workflow
        
    Returns:
        Execution result with status and outputs
    """
    from tasks.workflow_tasks import run_workflow
    
    logger.info(
        "Starting workflow execution",
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        trigger=trigger,
    )
    
    try:
        result = await run_workflow(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            input_data=input_data or {},
            redis=ctx["redis"],
        )
        
        logger.info(
            "Workflow completed",
            workflow_id=workflow_id,
            status=result.get("status"),
            steps_completed=result.get("steps_completed", 0),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Workflow failed",
            workflow_id=workflow_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "error": str(e),
            "workflow_id": workflow_id,
        }


async def execute_agent_task(
    ctx: Dict[str, Any],
    agent_id: str,
    tenant_id: str,
    task_type: str,
    input_data: Dict[str, Any],
    conversation_id: str = None,
) -> Dict[str, Any]:
    """
    Execute an agent task using LangGraph.
    
    Args:
        ctx: ARQ context
        agent_id: ID of the agent to use
        tenant_id: Tenant ID
        task_type: Type of task (chat, analyze, generate, etc.)
        input_data: Task input
        conversation_id: Optional conversation for context
        
    Returns:
        Agent response with content and metadata
    """
    from graphs.tool_agent import create_tool_agent_graph
    
    logger.info(
        "Starting agent task",
        agent_id=agent_id,
        tenant_id=tenant_id,
        task_type=task_type,
    )
    
    try:
        # Create agent graph
        graph = await create_tool_agent_graph(
            agent_id=agent_id,
            tenant_id=tenant_id,
        )
        
        # Execute
        result = await graph.ainvoke({
            "messages": [{"role": "user", "content": input_data.get("message", "")}],
            "task_type": task_type,
            "tenant_id": tenant_id,
        })
        
        logger.info(
            "Agent task completed",
            agent_id=agent_id,
            output_length=len(result.get("output", "")),
        )
        
        return {
            "status": "success",
            "output": result.get("output"),
            "messages": result.get("messages", []),
            "tools_used": result.get("tools_used", []),
        }
        
    except Exception as e:
        logger.error(
            "Agent task failed",
            agent_id=agent_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "error": str(e),
        }


async def send_scheduled_email(
    ctx: Dict[str, Any],
    tenant_id: str,
    template_id: str,
    recipients: list,
    variables: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a scheduled email using a prompt template."""
    from tasks.scheduled_tasks import process_scheduled_email
    
    logger.info(
        "Sending scheduled email",
        tenant_id=tenant_id,
        template_id=template_id,
        recipient_count=len(recipients),
    )
    
    return await process_scheduled_email(
        tenant_id=tenant_id,
        template_id=template_id,
        recipients=recipients,
        variables=variables,
    )


# ============================================================
# CRON JOBS (Scheduled Tasks)
# ============================================================

async def check_pending_workflows(ctx: Dict[str, Any]):
    """Check and trigger pending scheduled workflows."""
    from tasks.scheduled_tasks import process_pending_workflows
    
    logger.debug("Checking pending workflows")
    await process_pending_workflows(ctx["redis"])


async def cleanup_old_executions(ctx: Dict[str, Any]):
    """Clean up old workflow execution logs."""
    from tasks.scheduled_tasks import cleanup_executions
    
    logger.info("Running execution cleanup")
    await cleanup_executions(days_to_keep=30)


# ============================================================
# WORKER LIFECYCLE
# ============================================================

async def startup(ctx: Dict[str, Any]):
    """Worker startup hook."""
    logger.info(
        "Worker starting",
        service=settings.SERVICE_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        max_jobs=settings.MAX_JOBS,
    )
    
    # Initialize database connection pool (read-only)
    # ctx["db"] = await create_db_pool()
    
    # Initialize LLM providers
    # ctx["llm_providers"] = initialize_llm_providers()


async def shutdown(ctx: Dict[str, Any]):
    """Worker shutdown hook."""
    logger.info("Worker shutting down")
    
    # Cleanup resources
    # if "db" in ctx:
    #     await ctx["db"].close()


# ============================================================
# WORKER SETTINGS
# ============================================================

class WorkerSettings:
    """ARQ Worker configuration."""
    
    # Redis connection
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    
    # Available functions (tasks)
    functions = [
        execute_workflow,
        execute_agent_task,
        send_scheduled_email,
    ]
    
    # Cron jobs
    cron_jobs = [
        cron(check_pending_workflows, minute={0, 15, 30, 45}),  # Every 15 min
        cron(cleanup_old_executions, hour=3, minute=0),  # Daily at 3 AM
    ]
    
    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Worker settings
    max_jobs = settings.MAX_JOBS
    job_timeout = settings.JOB_TIMEOUT
    keep_result = 3600  # Keep results for 1 hour
    
    # Health check
    health_check_interval = 30
    
    # Queue names
    queue_name = "agent-saas:default"


# ============================================================
# HEALTH CHECK SERVER (optional)
# ============================================================

async def health_server():
    """Simple HTTP health check server."""
    from aiohttp import web
    
    async def health_handler(request):
        return web.json_response({
            "status": "healthy",
            "service": settings.SERVICE_NAME,
            "version": settings.VERSION,
        })
    
    app = web.Application()
    app.router.add_get("/health", health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.HEALTH_CHECK_PORT)
    await site.start()
    
    logger.info(f"Health check server on port {settings.HEALTH_CHECK_PORT}")


if __name__ == "__main__":
    # Run health server in background when running directly
    loop = asyncio.get_event_loop()
    loop.run_until_complete(health_server())
    
    # The actual worker is started by: arq main.WorkerSettings
    print(f"Worker settings configured. Run with: arq main.WorkerSettings")
