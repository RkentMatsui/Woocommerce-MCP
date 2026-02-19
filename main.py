from fastapi import FastAPI, Request, HTTPException, Header
from mcp.server.sse import SseServerTransport
from server import app
import uvicorn
import os
from typing import Optional

# Initialize FastAPI app
fastapi_app = FastAPI(title="Nova B2B MCP Server")

# Create SSE transport handler
# The endpoint "/messages" is where clients will post JSON-RPC messages
sse = SseServerTransport("/messages")

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify the API key from the header"""
    expected_key = os.getenv("MCP_SSE_API_KEY")
    if not expected_key:
        # If no key is set in environment, we might want to allow access or block all.
        # Given the request, we should probably require it to be set.
        raise HTTPException(status_code=500, detail="MCP_SSE_API_KEY not configured on server")
    
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

@fastapi_app.get("/sse")
async def handle_sse(request: Request, x_api_key: Optional[str] = Header(None)):
    """Handle SSE connections"""
    await verify_api_key(x_api_key)
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

@fastapi_app.post("/messages")
async def handle_messages(request: Request, x_api_key: Optional[str] = Header(None)):
    """Handle incoming JSON-RPC messages"""
    await verify_api_key(x_api_key)
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
