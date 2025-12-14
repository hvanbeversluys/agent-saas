"""
Scheduled Tasks - Periodic job implementations.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import structlog
from redis.asyncio import Redis

from config import settings

logger = structlog.get_logger()


async def process_pending_workflows(redis: Redis):
    """
    Check and trigger pending scheduled workflows.
    
    Runs every 15 minutes to check for workflows
    that should be triggered based on their schedule.
    """
    import httpx
    
    logger.debug("Checking pending scheduled workflows")
    
    try:
        # Get pending workflows from backend
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.BACKEND_URL}/api/scheduled-jobs/pending",
                timeout=10.0,
            )
            
            if response.status_code != 200:
                logger.warning(
                    "Failed to get pending workflows",
                    status_code=response.status_code,
                )
                return
            
            pending_jobs = response.json().get("jobs", [])
        
        logger.info(
            "Found pending workflows",
            count=len(pending_jobs),
        )
        
        # Queue each job for execution
        for job in pending_jobs:
            await queue_workflow_execution(
                redis=redis,
                workflow_id=job.get("workflow_id"),
                tenant_id=job.get("tenant_id"),
                trigger="schedule",
                job_id=job.get("id"),
            )
            
    except Exception as e:
        logger.error("Failed to process pending workflows", error=str(e))


async def queue_workflow_execution(
    redis: Redis,
    workflow_id: str,
    tenant_id: str,
    trigger: str = "schedule",
    job_id: str = None,
    input_data: Dict[str, Any] = None,
):
    """
    Queue a workflow for execution.
    
    Args:
        redis: Redis connection
        workflow_id: Workflow to execute
        tenant_id: Tenant ID
        trigger: What triggered the execution
        job_id: Optional scheduled job ID
        input_data: Optional input data
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    
    pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    await pool.enqueue_job(
        "execute_workflow",
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        trigger=trigger,
        input_data=input_data or {},
    )
    
    logger.info(
        "Workflow queued",
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        trigger=trigger,
    )
    
    await pool.close()


async def process_scheduled_email(
    tenant_id: str,
    template_id: str,
    recipients: List[str],
    variables: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a scheduled email using a prompt template.
    
    Args:
        tenant_id: Tenant ID
        template_id: Prompt template ID
        recipients: Email recipients
        variables: Variables for template
        
    Returns:
        Send result
    """
    from tools.email import EmailTool
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage
    
    logger.info(
        "Processing scheduled email",
        tenant_id=tenant_id,
        template_id=template_id,
        recipient_count=len(recipients),
    )
    
    try:
        # Load template from backend
        template = await load_prompt_template(template_id, tenant_id)
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Substitute variables in template
        prompt = template.get("template", "")
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        
        # Generate email content with LLM
        llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
        )
        
        response = await llm.ainvoke([
            HumanMessage(content=f"Génère un email professionnel basé sur: {prompt}")
        ])
        
        email_content = response.content
        
        # Parse subject and body from response
        # Assuming format: "Objet: ...\n\n..."
        lines = email_content.strip().split("\n", 2)
        subject = lines[0].replace("Objet:", "").replace("Subject:", "").strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else email_content
        
        # Send email
        email_tool = EmailTool(
            tenant_id=tenant_id,
            config={"email_provider": "mock"},  # TODO: Load from tenant config
        )
        
        result = await email_tool.run(
            to=recipients,
            subject=subject or "Email automatique",
            body=body,
        )
        
        return {
            "status": "sent",
            "recipients": recipients,
            "subject": subject,
            "result": result,
        }
        
    except Exception as e:
        logger.error(
            "Scheduled email failed",
            template_id=template_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "error": str(e),
        }


async def load_prompt_template(
    template_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """Load prompt template from backend."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.BACKEND_URL}/api/prompts/{template_id}",
                headers={"X-Tenant-ID": tenant_id},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
    except Exception as e:
        logger.error("Failed to load template", error=str(e))
        return None


async def cleanup_executions(days_to_keep: int = 30):
    """
    Clean up old workflow execution logs.
    
    Args:
        days_to_keep: Number of days to keep logs
    """
    import httpx
    
    cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
    
    logger.info(
        "Cleaning up old executions",
        cutoff_date=cutoff_date,
        days_to_keep=days_to_keep,
    )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{settings.BACKEND_URL}/api/admin/executions/cleanup",
                params={"before": cutoff_date},
                timeout=30.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(
                    "Cleanup completed",
                    deleted_count=result.get("deleted", 0),
                )
            else:
                logger.warning(
                    "Cleanup request failed",
                    status_code=response.status_code,
                )
                
    except Exception as e:
        logger.error("Cleanup failed", error=str(e))


async def send_daily_reports(redis: Redis):
    """
    Send daily summary reports to tenants.
    
    This would be a cron job running daily.
    """
    # TODO: Implement daily reports
    logger.info("Daily reports task - not implemented yet")


async def sync_external_data(redis: Redis):
    """
    Sync data from external sources (CRM, calendar, etc).
    
    This would run periodically to keep data fresh.
    """
    # TODO: Implement data sync
    logger.info("External data sync - not implemented yet")
