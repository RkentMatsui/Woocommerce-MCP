import asyncio
import os
from datetime import datetime, timedelta
from typing import Any
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from woocommerce import API
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize WooCommerce API client
wcapi = API(
    url=os.getenv("WC_URL"),
    consumer_key=os.getenv("WC_CONSUMER_KEY"),
    consumer_secret=os.getenv("WC_CONSUMER_SECRET"),
    version="wc/v3",
    timeout=30
)

# Create MCP server
app = Server("woocommerce-analytics")

# Helper function to safely call WooCommerce API
def wc_get(endpoint: str, params: dict = None) -> dict:
    """Safely fetch data from WooCommerce API"""
    try:
        response = wcapi.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Tool 1: Get Products
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls from Claude"""
    
    if name == "get_products":
        per_page = arguments.get("per_page", 10)
        category = arguments.get("category", None)
        
        params = {"per_page": per_page}
        if category:
            params["category"] = category
            
        products = wc_get("products", params)
        
        if "error" in products:
            return [TextContent(type="text", text=f"Error: {products['error']}")]
        
        # Format product data
        result = []
        for p in products:
            result.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "sku": p.get("sku"),
                "price": p.get("price"),
                "stock_quantity": p.get("stock_quantity"),
                "total_sales": p.get("total_sales", 0)
            })
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    elif name == "get_orders":
        per_page = arguments.get("per_page", 10)
        status = arguments.get("status", "any")
        after = arguments.get("after", None)
        before = arguments.get("before", None)
        
        params = {"per_page": per_page, "status": status}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
            
        orders = wc_get("orders", params)
        
        if "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
        
        # Format order data
        result = []
        for o in orders:
            result.append({
                "id": o.get("id"),
                "status": o.get("status"),
                "total": o.get("total"),
                "date_created": o.get("date_created"),
                "customer_id": o.get("customer_id"),
                "line_items": len(o.get("line_items", []))
            })
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    elif name == "analyze_sales_trends":
        days = arguments.get("days", 30)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Fetch orders
        params = {
            "per_page": 100,
            "after": start_date.isoformat(),
            "before": end_date.isoformat(),
            "status": "completed"
        }
        
        orders = wc_get("orders", params)
        
        if "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
        
        if not orders:
            return [TextContent(type="text", text="No orders found in date range")]
        
        # Analyze with pandas
        df = pd.DataFrame([{
            "date": o.get("date_created"),
            "total": float(o.get("total", 0)),
            "items": len(o.get("line_items", []))
        } for o in orders])
        
        df['date'] = pd.to_datetime(df['date'])
        df['date_only'] = df['date'].dt.date
        
        # Calculate metrics
        daily_sales = df.groupby('date_only').agg({
            'total': 'sum',
            'items': 'sum'
        }).reset_index()
        
        analysis = {
            "total_orders": len(orders),
            "total_revenue": float(df['total'].sum()),
            "average_order_value": float(df['total'].mean()),
            "average_items_per_order": float(df['items'].mean()),
            "daily_average_revenue": float(daily_sales['total'].mean()),
            "best_day": {
                "date": str(daily_sales.loc[daily_sales['total'].idxmax(), 'date_only']),
                "revenue": float(daily_sales['total'].max())
            }
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(analysis, indent=2)
        )]
    
    elif name == "get_low_stock_products":
        threshold = arguments.get("threshold", 10)
        
        # Get all products (paginated)
        all_products = []
        page = 1
        per_page = 100
        
        while True:
            products = wc_get("products", {"per_page": per_page, "page": page})
            if "error" in products or not products:
                break
            all_products.extend(products)
            if len(products) < per_page:
                break
            page += 1
        
        # Filter low stock
        low_stock = []
        for p in all_products:
            stock_qty = p.get("stock_quantity")
            if stock_qty is not None and stock_qty <= threshold:
                low_stock.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "sku": p.get("sku"),
                    "stock_quantity": stock_qty,
                    "price": p.get("price"),
                    "manage_stock": p.get("manage_stock")
                })
        
        # Sort by stock quantity
        low_stock.sort(key=lambda x: x["stock_quantity"])
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "total_low_stock_products": len(low_stock),
                "threshold": threshold,
                "products": low_stock
            }, indent=2)
        )]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

# Register available tools
@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="get_products",
            description="Get products from WooCommerce store. Returns product details including ID, name, SKU, price, stock quantity, and total sales.",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "number",
                        "description": "Number of products to retrieve (max 100)",
                        "default": 10
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category ID (optional)"
                    }
                }
            }
        ),
        Tool(
            name="get_orders",
            description="Get orders from WooCommerce store. Returns order details including status, total, date, and customer info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "number",
                        "description": "Number of orders to retrieve (max 100)",
                        "default": 10
                    },
                    "status": {
                        "type": "string",
                        "description": "Order status: any, pending, processing, on-hold, completed, cancelled, refunded, failed",
                        "default": "any"
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO 8601 date to get orders after (e.g., 2024-01-01T00:00:00)"
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO 8601 date to get orders before"
                    }
                }
            }
        ),
        Tool(
            name="analyze_sales_trends",
            description="Analyze sales trends over a specified time period. Returns total orders, revenue, averages, and best performing day.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "number",
                        "description": "Number of days to analyze (default 30)",
                        "default": 30
                    }
                }
            }
        ),
        Tool(
            name="get_low_stock_products",
            description="Find products with low stock levels. Useful for inventory management and reorder alerts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Stock quantity threshold (products at or below this level)",
                        "default": 10
                    }
                }
            }
        )
    ]

# Main function to run the server
async def main():
    """Run the MCP server using stdio transport"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())