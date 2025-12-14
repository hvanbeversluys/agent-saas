"""
Email Tool - Send emails via various providers.
"""
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import structlog

from tools.base import BaseTool

logger = structlog.get_logger()


class EmailInput(BaseModel):
    """Input schema for email tool."""
    to: List[str]  # List of recipient emails
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    html: bool = False  # If true, body is HTML


class EmailTool(BaseTool):
    """
    Tool for sending emails.
    
    Supports multiple providers:
    - SMTP (generic)
    - Gmail API
    - SendGrid
    - Mailgun
    """
    
    name = "send_email"
    description = (
        "Envoie un email à un ou plusieurs destinataires. "
        "Utilisez cet outil pour envoyer des emails professionnels, "
        "relances, newsletters, etc."
    )
    args_schema = EmailInput
    
    def get_required_config(self) -> list:
        return ["email_provider", "api_key"]  # or smtp_host, smtp_port, etc.
    
    async def _execute(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        html: bool = False,
    ) -> dict:
        """
        Send an email.
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: CC recipients
            bcc: BCC recipients
            html: Whether body is HTML
            
        Returns:
            Dict with send status and message_id
        """
        provider = self.config.get("email_provider", "smtp")
        
        logger.info(
            "Sending email",
            provider=provider,
            to=to,
            subject=subject,
        )
        
        if provider == "smtp":
            return await self._send_smtp(to, subject, body, cc, bcc, html)
        elif provider == "sendgrid":
            return await self._send_sendgrid(to, subject, body, cc, bcc, html)
        elif provider == "gmail":
            return await self._send_gmail(to, subject, body, cc, bcc, html)
        else:
            # Mock for development
            return await self._mock_send(to, subject, body)
    
    async def _mock_send(
        self,
        to: List[str],
        subject: str,
        body: str,
    ) -> dict:
        """Mock email sending for development."""
        logger.info(
            "MOCK: Email would be sent",
            to=to,
            subject=subject,
            body_preview=body[:100],
        )
        
        return {
            "status": "mock_sent",
            "message_id": f"mock-{hash(subject)}",
            "recipients": to,
            "note": "Email not actually sent (mock mode)",
        }
    
    async def _send_smtp(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        html: bool = False,
    ) -> dict:
        """Send email via SMTP."""
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        smtp_host = self.config.get("smtp_host", "localhost")
        smtp_port = self.config.get("smtp_port", 587)
        smtp_user = self.config.get("smtp_user")
        smtp_pass = self.config.get("smtp_pass")
        from_email = self.config.get("from_email", smtp_user)
        
        # Build message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = ", ".join(to)
        
        if cc:
            msg["Cc"] = ", ".join(cc)
        
        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type))
        
        # Send
        try:
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_pass,
                start_tls=True,
            )
            
            return {
                "status": "sent",
                "message_id": msg["Message-ID"],
                "recipients": to,
            }
            
        except Exception as e:
            logger.error("SMTP send failed", error=str(e))
            raise
    
    async def _send_sendgrid(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        html: bool = False,
    ) -> dict:
        """Send email via SendGrid API."""
        import httpx
        
        api_key = self.config.get("api_key")
        from_email = self.config.get("from_email")
        
        payload = {
            "personalizations": [{
                "to": [{"email": email} for email in to],
            }],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{
                "type": "text/html" if html else "text/plain",
                "value": body,
            }],
        }
        
        if cc:
            payload["personalizations"][0]["cc"] = [{"email": e} for e in cc]
        if bcc:
            payload["personalizations"][0]["bcc"] = [{"email": e} for e in bcc]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            
            return {
                "status": "sent",
                "message_id": response.headers.get("X-Message-Id"),
                "recipients": to,
            }
    
    async def _send_gmail(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        html: bool = False,
    ) -> dict:
        """Send email via Gmail API."""
        # TODO: Implement Gmail API
        return await self._mock_send(to, subject, body)
