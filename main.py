from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.sse import SseServerTransport
from server import app
import uvicorn
import os
from typing import Optional

# Initialize FastAPI app
fastapi_app = FastAPI(title="Nova B2B MCP Server")

# Add CORS middleware to allow web-based MCP clients
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create SSE transport handler
# The endpoint "/messages" is where clients will post JSON-RPC messages
sse = SseServerTransport("/messages")

async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None)
):
    """Verify the API key from the header or query parameter"""
    expected_key = os.getenv("MCP_SSE_API_KEY")
    
    # Debug logging for Render
    print(f"DEBUG: Request Path: {request.url.path}")
    print(f"DEBUG: Headers present: {list(request.headers.keys())}")
    print(f"DEBUG: X-API-Key in Header: {'Yes' if x_api_key else 'No'}")
    print(f"DEBUG: api_key in Query: {'Yes' if api_key else 'No'}")
    
    if not expected_key:
        print("CRITICAL ERROR: MCP_SSE_API_KEY environment variable is NOT SET in Render/Local environment.")
        raise HTTPException(status_code=500, detail="Server security not configured")
    
    provided_key = x_api_key or api_key
    
    if provided_key != expected_key:
        print(f"AUTH FAILED: Key provided: {'Yes' if provided_key else 'No'}")
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    print("AUTH SUCCESSFUL")

@fastapi_app.get("/sse")
async def handle_sse(
    request: Request, 
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None)
):
    """Handle SSE connections"""
    await verify_api_key(request, x_api_key, api_key)
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

@fastapi_app.post("/messages")
async def handle_messages(
    request: Request, 
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None)
):
    """Handle incoming JSON-RPC messages"""
    await verify_api_key(request, x_api_key, api_key)
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
