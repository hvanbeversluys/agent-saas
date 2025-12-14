"""
CRM Tool - Interact with CRM systems.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import structlog

from tools.base import BaseTool

logger = structlog.get_logger()


class CRMContactInput(BaseModel):
    """Input for CRM contact operations."""
    action: str = "get"  # get, create, update, search
    contact_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


class CRMDealInput(BaseModel):
    """Input for CRM deal operations."""
    action: str = "get"  # get, create, update, search
    deal_id: Optional[str] = None
    contact_id: Optional[str] = None
    title: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None
    expected_close: Optional[str] = None


class CRMTool(BaseTool):
    """
    Tool for CRM interactions.
    
    Supports:
    - HubSpot
    - Pipedrive
    - Notion (as CRM)
    - Airtable
    """
    
    name = "crm"
    description = (
        "Interagit avec le CRM pour gérer contacts, deals et pipelines. "
        "Peut créer, mettre à jour et rechercher des données client."
    )
    args_schema = CRMContactInput
    
    def get_required_config(self) -> list:
        return ["crm_type", "api_key"]
    
    async def _execute(
        self,
        action: str = "get",
        contact_id: str = None,
        email: str = None,
        name: str = None,
        company: str = None,
        phone: str = None,
        status: str = None,
        notes: str = None,
        custom_fields: Dict[str, Any] = None,
    ) -> dict:
        """
        Execute CRM operation.
        
        Args:
            action: Operation type
            contact_id: Contact ID for get/update
            email: Contact email
            name: Contact name
            company: Company name
            phone: Phone number
            status: Contact status
            notes: Notes about contact
            custom_fields: Additional fields
            
        Returns:
            Operation result
        """
        crm_type = self.config.get("crm_type", "mock")
        
        logger.info(
            "CRM operation",
            crm_type=crm_type,
            action=action,
            contact_id=contact_id,
        )
        
        if action == "get":
            return await self._get_contact(crm_type, contact_id, email)
        elif action == "create":
            return await self._create_contact(
                crm_type, email, name, company, phone, status, notes, custom_fields
            )
        elif action == "update":
            return await self._update_contact(
                crm_type, contact_id, email, name, company, phone, status, notes, custom_fields
            )
        elif action == "search":
            return await self._search_contacts(crm_type, email, name, company)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _get_contact(
        self,
        crm_type: str,
        contact_id: str = None,
        email: str = None,
    ) -> dict:
        """Get a contact from CRM."""
        if crm_type == "hubspot":
            return await self._hubspot_get_contact(contact_id, email)
        elif crm_type == "pipedrive":
            return await self._pipedrive_get_contact(contact_id, email)
        else:
            # Mock response
            return {
                "status": "mock_found",
                "contact": {
                    "id": contact_id or "mock-123",
                    "email": email or "mock@example.com",
                    "name": "Mock Contact",
                    "company": "Mock Company",
                    "status": "lead",
                },
                "note": "Contact data is mock",
            }
    
    async def _create_contact(
        self,
        crm_type: str,
        email: str,
        name: str,
        company: str,
        phone: str,
        status: str,
        notes: str,
        custom_fields: Dict[str, Any],
    ) -> dict:
        """Create a new contact in CRM."""
        logger.info(
            "Creating CRM contact",
            crm_type=crm_type,
            email=email,
            name=name,
        )
        
        if crm_type == "hubspot":
            return await self._hubspot_create_contact(
                email, name, company, phone, status, notes, custom_fields
            )
        else:
            # Mock response
            return {
                "status": "mock_created",
                "contact_id": f"mock-{hash(email)}",
                "email": email,
                "name": name,
                "note": "Contact not actually created (mock mode)",
            }
    
    async def _update_contact(
        self,
        crm_type: str,
        contact_id: str,
        email: str = None,
        name: str = None,
        company: str = None,
        phone: str = None,
        status: str = None,
        notes: str = None,
        custom_fields: Dict[str, Any] = None,
    ) -> dict:
        """Update an existing contact."""
        return {
            "status": "mock_updated",
            "contact_id": contact_id,
            "note": "Contact not actually updated (mock mode)",
        }
    
    async def _search_contacts(
        self,
        crm_type: str,
        email: str = None,
        name: str = None,
        company: str = None,
    ) -> dict:
        """Search contacts in CRM."""
        return {
            "status": "mock_search",
            "results": [],
            "total": 0,
            "note": "Search not implemented (mock mode)",
        }
    
    async def _hubspot_get_contact(
        self,
        contact_id: str = None,
        email: str = None,
    ) -> dict:
        """Get contact from HubSpot."""
        import httpx
        
        api_key = self.config.get("api_key")
        
        async with httpx.AsyncClient() as client:
            if contact_id:
                url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
            elif email:
                url = f"https://api.hubapi.com/crm/v3/objects/contacts/{email}?idProperty=email"
            else:
                raise ValueError("Either contact_id or email required")
            
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                params={"properties": "email,firstname,lastname,company,phone,hs_lead_status"},
            )
            response.raise_for_status()
            data = response.json()
            
            props = data.get("properties", {})
            return {
                "status": "found",
                "contact": {
                    "id": data.get("id"),
                    "email": props.get("email"),
                    "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                    "company": props.get("company"),
                    "phone": props.get("phone"),
                    "status": props.get("hs_lead_status"),
                },
            }
    
    async def _hubspot_create_contact(
        self,
        email: str,
        name: str,
        company: str,
        phone: str,
        status: str,
        notes: str,
        custom_fields: Dict[str, Any],
    ) -> dict:
        """Create contact in HubSpot."""
        import httpx
        
        api_key = self.config.get("api_key")
        
        # Parse name
        name_parts = (name or "").split(" ", 1)
        firstname = name_parts[0] if name_parts else ""
        lastname = name_parts[1] if len(name_parts) > 1 else ""
        
        properties = {
            "email": email,
            "firstname": firstname,
            "lastname": lastname,
        }
        
        if company:
            properties["company"] = company
        if phone:
            properties["phone"] = phone
        if status:
            properties["hs_lead_status"] = status
        if notes:
            properties["notes"] = notes
        if custom_fields:
            properties.update(custom_fields)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"properties": properties},
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "created",
                "contact_id": data.get("id"),
                "email": email,
                "name": name,
            }
    
    async def _pipedrive_get_contact(
        self,
        contact_id: str = None,
        email: str = None,
    ) -> dict:
        """Get contact from Pipedrive."""
        # TODO: Implement Pipedrive API
        return {
            "status": "not_implemented",
            "note": "Pipedrive integration coming soon",
        }
