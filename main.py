from fastapi import FastAPI, Request
from mcp.server.sse import SseServerTransport
from server import app
import uvicorn
import os

# Initialize FastAPI app
fastapi_app = FastAPI(title="Nova B2B MCP Server")

# Create SSE transport handler
# The endpoint "/messages" is where clients will post JSON-RPC messages
sse = SseServerTransport("/messages")

@fastapi_app.get("/sse")
async def handle_sse(request: Request):
    """Handle SSE connections"""
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

@fastapi_app.post("/messages")
async def handle_messages(request: Request):
    """Handle incoming JSON-RPC messages"""
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
