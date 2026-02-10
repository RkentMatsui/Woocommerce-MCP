import os
import requests
import base64
import json
from typing import Any
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

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

ZENDESK_DOMAIN = "novasignagehelp.zendesk.com"
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")

def get_zendesk_auth():
    if not ZENDESK_EMAIL or not ZENDESK_API_TOKEN:
        return None
    auth_str = f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return f"Basic {encoded_auth}"

def zendesk_request(method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
    """Safely make requests to Zendesk API"""
    url = f"https://{ZENDESK_DOMAIN}/api/v2/{endpoint.lstrip('/')}"
    auth = get_zendesk_auth()
    
    if not auth:
        return {"error": "Zendesk credentials (ZENDESK_EMAIL, ZENDESK_API_TOKEN) not found in .env"}
        
    headers = {
        "Authorization": auth,
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
            return {"error": response.json().get("description", str(e))}
        except:
            return {"error": str(e)}

async def handle_zendesk_tool(name: str, arguments: Any) -> list[TextContent]:
    if name == "search_zendesk_tickets":
        query = arguments.get("query")
        if not query:
            return [TextContent(type="text", text="Error: query is required")]
        
        result = zendesk_request("GET", "search.json", params={"query": query})
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_zendesk_ticket":
        ticket_id = arguments.get("ticket_id")
        if not ticket_id:
            return [TextContent(type="text", text="Error: ticket_id is required")]
            
        result = zendesk_request("GET", f"tickets/{ticket_id}.json")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "add_zendesk_ticket_comment":
        ticket_id = arguments.get("ticket_id")
        comment = arguments.get("comment")
        public = arguments.get("public", True)
        
        if not ticket_id or not comment:
            return [TextContent(type="text", text="Error: ticket_id and comment are required")]
            
        data = {
            "ticket": {
                "comment": {
                    "body": comment,
                    "public": public
                }
            }
        }
        result = zendesk_request("PUT", f"tickets/{ticket_id}.json", data=data)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "search_zendesk_users":
        query = arguments.get("query")
        if not query:
            return [TextContent(type="text", text="Error: query is required")]
            
        result = zendesk_request("GET", "users/search.json", params={"query": query})
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_zendesk_ticket_comments":
        ticket_id = arguments.get("ticket_id")
        if not ticket_id:
            return [TextContent(type="text", text="Error: ticket_id is required")]
            
        result = zendesk_request("GET", f"tickets/{ticket_id}/comments.json")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return []

def get_zendesk_tool_definitions() -> list[Tool]:
    return [
        Tool(
            name="search_zendesk_tickets",
            description="Search for Zendesk tickets using Zendesk search query syntax.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Zendesk search query (e.g. 'status<solved order_id:12345')"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_zendesk_ticket",
            description="Get details of a specific Zendesk ticket by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The Zendesk ticket ID"}
                },
                "required": ["ticket_id"]
            }
        ),
        Tool(
            name="get_zendesk_ticket_comments",
            description="Retrieve all comments for a specific Zendesk ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The Zendesk ticket ID"}
                },
                "required": ["ticket_id"]
            }
        ),
        Tool(
            name="add_zendesk_ticket_comment",
            description="Add a comment (reply or internal note) to a Zendesk ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The Zendesk ticket ID"},
                    "comment": {"type": "string", "description": "The comment text"},
                    "public": {"type": "boolean", "default": True, "description": "Whether the comment is public (visible to requester) or internal"}
                },
                "required": ["ticket_id", "comment"]
            }
        ),
        Tool(
            name="search_zendesk_users",
            description="Search for Zendesk users by email, name, or phone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for users"}
                },
                "required": ["query"]
            }
        )
    ]
