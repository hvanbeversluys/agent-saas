"""
Calendar Tool - Manage calendar events.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import structlog

from tools.base import BaseTool

logger = structlog.get_logger()


class CalendarEventInput(BaseModel):
    """Input schema for creating calendar events."""
    title: str
    description: Optional[str] = None
    start_time: str  # ISO format
    end_time: Optional[str] = None  # ISO format, defaults to start + 1h
    attendees: Optional[List[str]] = None  # Email addresses
    location: Optional[str] = None
    reminder_minutes: Optional[int] = 15


class CalendarQueryInput(BaseModel):
    """Input for querying calendar."""
    start_date: str  # ISO format
    end_date: Optional[str] = None
    query: Optional[str] = None


class CalendarTool(BaseTool):
    """
    Tool for managing calendar events.
    
    Supports:
    - Google Calendar
    - Outlook Calendar
    - CalDAV (generic)
    """
    
    name = "calendar"
    description = (
        "Gère les événements du calendrier. "
        "Peut créer, modifier, supprimer des rendez-vous "
        "et consulter les disponibilités."
    )
    args_schema = CalendarEventInput
    
    def get_required_config(self) -> list:
        return ["calendar_provider", "oauth_token"]
    
    async def _execute(
        self,
        title: str,
        description: str = None,
        start_time: str = None,
        end_time: str = None,
        attendees: List[str] = None,
        location: str = None,
        reminder_minutes: int = 15,
        action: str = "create",  # create, list, delete
    ) -> dict:
        """
        Execute calendar operation.
        
        Args:
            title: Event title
            description: Event description
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            attendees: List of attendee emails
            location: Event location
            reminder_minutes: Reminder before event
            action: Operation to perform
            
        Returns:
            Operation result
        """
        provider = self.config.get("calendar_provider", "mock")
        
        if action == "create":
            return await self._create_event(
                provider, title, description, start_time, end_time,
                attendees, location, reminder_minutes
            )
        elif action == "list":
            return await self._list_events(provider, start_time, end_time)
        elif action == "delete":
            return await self._delete_event(provider, title)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _create_event(
        self,
        provider: str,
        title: str,
        description: str,
        start_time: str,
        end_time: str,
        attendees: List[str],
        location: str,
        reminder_minutes: int,
    ) -> dict:
        """Create a calendar event."""
        logger.info(
            "Creating calendar event",
            provider=provider,
            title=title,
            start_time=start_time,
        )
        
        # Parse times
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if end_time:
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        else:
            end = start + timedelta(hours=1)
        
        if provider == "google":
            return await self._create_google_event(
                title, description, start, end, attendees, location, reminder_minutes
            )
        else:
            # Mock response
            return {
                "status": "mock_created",
                "event_id": f"mock-event-{hash(title)}",
                "title": title,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "attendees": attendees or [],
                "note": "Event not actually created (mock mode)",
            }
    
    async def _create_google_event(
        self,
        title: str,
        description: str,
        start: datetime,
        end: datetime,
        attendees: List[str],
        location: str,
        reminder_minutes: int,
    ) -> dict:
        """Create event via Google Calendar API."""
        import httpx
        
        oauth_token = self.config.get("oauth_token")
        
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Paris"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Paris"},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            },
        }
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        if location:
            event["location"] = location
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {oauth_token}"},
                json=event,
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "created",
                "event_id": data.get("id"),
                "html_link": data.get("htmlLink"),
                "title": title,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
    
    async def _list_events(
        self,
        provider: str,
        start_time: str,
        end_time: str,
    ) -> dict:
        """List calendar events in date range."""
        # TODO: Implement for each provider
        return {
            "status": "mock_list",
            "events": [],
            "note": "Event listing not implemented",
        }
    
    async def _delete_event(self, provider: str, event_id: str) -> dict:
        """Delete a calendar event."""
        # TODO: Implement for each provider
        return {
            "status": "mock_deleted",
            "event_id": event_id,
            "note": "Event not actually deleted (mock mode)",
        }
