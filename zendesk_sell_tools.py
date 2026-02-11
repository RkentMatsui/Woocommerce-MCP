import os
import requests
import json
from typing import Any
from mcp.types import Tool, TextContent

# Manual .env parsing to ensure we get the right values
def load_env_manually(path):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_env_manually(env_path)

ZENDESK_SELL_API_TOKEN = os.getenv("ZENDESK_SELL_API_TOKEN")
BASE_URL = "https://api.getbase.com/v2"

def get_zendesk_sell_auth():
    if not ZENDESK_SELL_API_TOKEN:
        return None
    return f"Bearer {ZENDESK_SELL_API_TOKEN}"

def zendesk_sell_request(method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
    """Safely make requests to Zendesk Sell API"""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    auth = get_zendesk_sell_auth()
    
    if not auth:
        return {"error": "Zendesk Sell API token (ZENDESK_SELL_API_TOKEN) not found in .env"}
        
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {"success": True}
        return response.json()
    except Exception as e:
        try:
            return {"error": response.json().get("errors", str(e))}
        except:
            return {"error": str(e)}

async def handle_zendesk_sell_tool(name: str, arguments: Any) -> list[TextContent]:
    if name == "search_zendesk_sell_leads":
        # Zendesk Sell leads search uses query params like email, last_name, etc.
        # Or a more general search if supported by their API
        params = {k: v for k, v in arguments.items() if v is not None}
        result = zendesk_sell_request("GET", "leads", params=params)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_zendesk_sell_lead":
        lead_id = arguments.get("lead_id")
        if not lead_id:
            return [TextContent(type="text", text="Error: lead_id is required")]
        result = zendesk_sell_request("GET", f"leads/{lead_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "search_zendesk_sell_contacts":
        params = {k: v for k, v in arguments.items() if v is not None}
        result = zendesk_sell_request("GET", "contacts", params=params)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_zendesk_sell_contact":
        contact_id = arguments.get("contact_id")
        if not contact_id:
            return [TextContent(type="text", text="Error: contact_id is required")]
        result = zendesk_sell_request("GET", f"contacts/{contact_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "search_zendesk_sell_deals":
        params = {k: v for k, v in arguments.items() if v is not None}
        result = zendesk_sell_request("GET", "deals", params=params)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_zendesk_sell_deal":
        deal_id = arguments.get("deal_id")
        if not deal_id:
            return [TextContent(type="text", text="Error: deal_id is required")]
        result = zendesk_sell_request("GET", f"deals/{deal_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Field-specific tools for Contacts
    field_tools = {
        "get_zendesk_sell_contact_industry": "industry",
        "get_zendesk_sell_contact_client": "Client",
        "get_zendesk_sell_contact_equipment": "Equipment",
        "get_zendesk_sell_contact_sample_box": "Sample Box",
        "get_zendesk_sell_contact_product": "Product",
        "get_zendesk_sell_contact_service": "Service",
        "get_zendesk_sell_contact_nova_web_id": "NOVA Web ID",
        "get_zendesk_sell_contact_journey_of_acquisition": "Journey of Acquisition",
        "get_zendesk_sell_contact_completed_web_training": "Completed Web Training",
        "get_zendesk_sell_contact_current_suppliers": "Current Suppliers"
    }

    if name in field_tools:
        contact_id = arguments.get("contact_id")
        if not contact_id:
            return [TextContent(type="text", text="Error: contact_id is required")]
        
        field_name = field_tools[name]
        result = zendesk_sell_request("GET", f"contacts/{contact_id}")
        
        if "error" in result:
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        data = result.get("data", {})
        custom_fields = data.get("custom_fields", {})
        
        # Check standard fields first (like industry), then custom fields
        value = data.get(field_name) or custom_fields.get(field_name)
        
        return [TextContent(type="text", text=json.dumps({
            "contact_id": contact_id,
            "field": field_name,
            "value": value
        }, indent=2))]

    return []

def get_zendesk_sell_tool_definitions() -> list[Tool]:
    tools = [
        Tool(
            name="search_zendesk_sell_leads",
            description="Search for leads in Zendesk Sell.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Filter by email"},
                    "first_name": {"type": "string", "description": "Filter by first name"},
                    "last_name": {"type": "string", "description": "Filter by last name"},
                    "organization_name": {"type": "string", "description": "Filter by organization name"}
                }
            }
        ),
        Tool(
            name="get_zendesk_sell_lead",
            description="Get details of a specific Zendesk Sell lead by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lead_id": {"type": "number", "description": "The Zendesk Sell lead ID"}
                },
                "required": ["lead_id"]
            }
        ),
        Tool(
            name="search_zendesk_sell_contacts",
            description="Search for contacts in Zendesk Sell.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Filter by email"},
                    "name": {"type": "string", "description": "Filter by name"},
                    "is_organization": {"type": "boolean", "description": "Filter by whether the contact is an organization"}
                }
            }
        ),
        Tool(
            name="get_zendesk_sell_contact",
            description="Get details of a specific Zendesk Sell contact by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "number", "description": "The Zendesk Sell contact ID"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="search_zendesk_sell_deals",
            description="Search for deals in Zendesk Sell.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Filter by deal name"},
                    "contact_id": {"type": "number", "description": "Filter by contact ID"}
                }
            }
        ),
        Tool(
            name="get_zendesk_sell_deal",
            description="Get details of a specific Zendesk Sell deal by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deal_id": {"type": "number", "description": "The Zendesk Sell deal ID"}
                },
                "required": ["deal_id"]
            }
        )
    ]

    # Add field-specific tools
    fields = [
        ("industry", "Industry"),
        ("client", "Client"),
        ("equipment", "Equipment"),
        ("sample_box", "Sample Box"),
        ("product", "Product"),
        ("service", "Service"),
        ("nova_web_id", "NOVA Web ID"),
        ("journey_of_acquisition", "Journey of Acquisition"),
        ("completed_web_training", "Completed Web Training"),
        ("current_suppliers", "Current Suppliers")
    ]

    for tool_suffix, display_name in fields:
        tools.append(Tool(
            name=f"get_zendesk_sell_contact_{tool_suffix}",
            description=f"Fetch the '{display_name}' field value for a specific Zendesk Sell contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "number", "description": "The Zendesk Sell contact ID"}
                },
                "required": ["contact_id"]
            }
        ))

    return tools
