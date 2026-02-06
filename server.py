import asyncio
import os
import requests
import base64
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

# Nova API Configuration
NOVA_API_URL = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/nova/v1"
NOVA_API_KEY = os.getenv("NOVA_API_KEY")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

def get_auth_headers(auth_type: str = "none") -> dict:
    headers = {}
    if auth_type == "api_key":
        if NOVA_API_KEY:
            headers["X-API-Key"] = NOVA_API_KEY
    elif auth_type == "basic":
        if WP_USERNAME and WP_APP_PASSWORD:
            auth_str = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"
    return headers

def nova_request(method: str, endpoint: str, params: dict = None, data: dict = None, auth_type: str = "none") -> dict:
    """Safely make requests to Nova B2B custom endpoints"""
    url = f"{NOVA_API_URL}/{endpoint.lstrip('/')}"
    headers = get_auth_headers(auth_type)
    
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
        return response.json()
    except Exception as e:
        try:
            return {"error": response.json().get("message", str(e))}
        except:
            return {"error": str(e)}

# Create MCP server
app = Server("woocommerce-analytics")

# Helper function to safely call WooCommerce API
def wc_request(method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
    """Safely make requests to WooCommerce API"""
    try:
        if method.lower() == "get":
            response = wcapi.get(endpoint, params=params)
        elif method.lower() == "post":
            response = wcapi.post(endpoint, data=data)
        elif method.lower() == "put":
            response = wcapi.put(endpoint, data=data)
        elif method.lower() == "delete":
            response = wcapi.delete(endpoint, params=params)
        else:
            return {"error": f"Unsupported method: {method}"}
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Check if it's a 4xx/5xx error with a JSON response from WC
        try:
            return {"error": response.json().get("message", str(e))}
        except:
            return {"error": str(e)}

def wc_get(endpoint: str, params: dict = None) -> dict:
    return wc_request("get", endpoint, params=params)

def wp_request(method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
    """Safely make requests to standard WordPress REST API"""
    url = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/wp/v2/{endpoint.lstrip('/')}"
    headers = get_auth_headers("basic") # Usually requires basic auth for all operations
    
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
        return response.json()
    except Exception as e:
        try:
            return {"error": response.json().get("message", str(e))}
        except:
            return {"error": str(e)}

def wp_get(endpoint: str, params: dict = None) -> dict:
    return wp_request("get", endpoint, params=params)


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
        search = arguments.get("search", None)
        customer = arguments.get("customer", None)
        
        params = {"per_page": per_page, "status": status}
        if after: params["after"] = after
        if before: params["before"] = before
        if search: params["search"] = search
        if customer: params["customer"] = customer
            
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
                "currency": o.get("currency"),
                "date_created": o.get("date_created"),
                "customer_id": o.get("customer_id"),
                "customer_note": o.get("customer_note"),
                "line_items": [{
                    "name": item.get("name"),
                    "quantity": item.get("quantity"),
                    "total": item.get("total")
                } for item in o.get("line_items", [])]
            })
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    elif name == "update_order_status":
        order_id = arguments.get("order_id")
        status = arguments.get("status")
        
        if not order_id or not status:
            return [TextContent(type="text", text="Error: order_id and status are required")]
            
        result = wc_request("put", f"orders/{order_id}", data={"status": status})
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(
            type="text",
            text=f"Successfully updated order {order_id} status to {status}."
        )]

    elif name == "get_order_notes":
        order_id = arguments.get("order_id")
        
        if not order_id:
            return [TextContent(type="text", text="Error: order_id is required")]
            
        notes = wc_get(f"orders/{order_id}/notes")
        
        if "error" in notes:
            return [TextContent(type="text", text=f"Error: {notes['error']}")]
            
        result = [{
            "id": n.get("id"),
            "date_created": n.get("date_created"),
            "author": n.get("author"),
            "note": n.get("note"),
            "customer_note": n.get("customer_note")
        } for n in notes]
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    elif name == "add_order_note":
        order_id = arguments.get("order_id")
        note = arguments.get("note")
        customer_note = arguments.get("customer_note", False)
        
        if not order_id or not note:
            return [TextContent(type="text", text="Error: order_id and note are required")]
            
        result = wc_request("post", f"orders/{order_id}/notes", data={
            "note": note,
            "customer_note": customer_note
        })
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(
            type="text",
            text=f"Successfully added note to order {order_id}."
        )]

    elif name == "create_order_refund":
        order_id = arguments.get("order_id")
        amount = arguments.get("amount")
        reason = arguments.get("reason", "")
        
        if not order_id or amount is None:
            return [TextContent(type="text", text="Error: order_id and amount are required")]
            
        result = wc_request("post", f"orders/{order_id}/refunds", data={
            "amount": str(amount),
            "reason": reason
        })
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(
            type="text",
            text=f"Successfully created refund of {amount} for order {order_id}."
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
    
    elif name == "get_frequent_buyers":
        order_threshold = arguments.get("order_threshold", 3)
        
        # Get recent orders to analyze
        orders = wc_get("orders", {"per_page": 100, "status": "completed"})
        
        if "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
            
        df = pd.DataFrame([{
            "customer_id": o.get("customer_id"),
            "customer_name": f"{o.get('billing', {}).get('first_name')} {o.get('billing', {}).get('last_name')}"
        } for o in orders if o.get("customer_id") != 0]) # Skip guest checkouts
        
        if df.empty:
            return [TextContent(type="text", text="No frequent buyers found in recent orders.")]
            
        freq = df.groupby(['customer_id', 'customer_name']).size().reset_index(name='order_count')
        frequent_buyers = freq[freq['order_count'] >= order_threshold].sort_values(by='order_count', ascending=False)
        
        return [TextContent(type="text", text=json.dumps(frequent_buyers.to_dict('records'), indent=2))]

    elif name == "update_product_stock":
        product_id = arguments.get("product_id")
        stock_quantity = arguments.get("stock_quantity")
        
        if not product_id or stock_quantity is None:
            return [TextContent(type="text", text="Error: product_id and stock_quantity are required")]
            
        result = wc_request("put", f"products/{product_id}", data={"stock_quantity": stock_quantity, "manage_stock": True})
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=f"Successfully updated product {product_id} stock to {stock_quantity}.")]

    elif name == "get_product_variations":
        product_id = arguments.get("product_id")
        
        if not product_id:
            return [TextContent(type="text", text="Error: product_id is required")]
            
        variations = wc_get(f"products/{product_id}/variations")
        
        if "error" in variations:
            return [TextContent(type="text", text=f"Error: {variations['error']}")]
            
        result = [{
            "id": v.get("id"),
            "sku": v.get("sku"),
            "price": v.get("price"),
            "stock_quantity": v.get("stock_quantity"),
            "attributes": v.get("attributes")
        } for v in variations]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "toggle_product_visibility":
        product_id = arguments.get("product_id")
        status = arguments.get("status") # 'publish', 'draft', 'pending', 'private'
        
        if not product_id or not status:
            return [TextContent(type="text", text="Error: product_id and status are required")]
            
        result = wc_request("put", f"products/{product_id}", data={"status": status})
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=f"Successfully set product {product_id} status to {status}.")]

    elif name == "create_coupon":
        code = arguments.get("code")
        amount = arguments.get("amount")
        discount_type = arguments.get("discount_type", "percent")
        description = arguments.get("description", "")
        
        if not code or not amount:
            return [TextContent(type="text", text="Error: code and amount are required")]
            
        result = wc_request("post", "coupons", data={
            "code": code,
            "amount": str(amount),
            "discount_type": discount_type,
            "description": description
        })
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=f"Successfully created coupon '{code}'.")]

    elif name == "get_active_coupons":
        coupons = wc_get("coupons", {"per_page": 100})
        
        if "error" in coupons:
            return [TextContent(type="text", text=f"Error: {coupons['error']}")]
            
        # Filter active (not expired)
        now = datetime.now()
        active = []
        for c in coupons:
            expiry = c.get("date_expires")
            if expiry:
                expiry_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                if expiry_dt > now:
                    active.append({
                        "id": c.get("id"),
                        "code": c.get("code"),
                        "amount": c.get("amount"),
                        "usage_count": c.get("usage_count"),
                        "date_expires": expiry
                    })
            else:
                active.append({
                    "id": c.get("id"),
                    "code": c.get("code"),
                    "amount": c.get("amount"),
                    "usage_count": c.get("usage_count"),
                    "date_expires": "No expiry"
                })
                
        return [TextContent(type="text", text=json.dumps(active, indent=2))]

    elif name == "get_all_orders":
        orders = nova_request("get", "nova_orders", auth_type="api_key")
        if "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
        return [TextContent(type="text", text=json.dumps(orders, indent=2))]

    elif name == "get_product_pricing":
        product_id = arguments.get("product_id")
        pricing_type = arguments.get("type", "letters") # letters, multi-letters, logos, quantity-discount
        
        endpoint_map = {
            "letters": f"pricingletters/{product_id}",
            "multi-letters": f"multipricingletters/{product_id}",
            "logos": f"pricinglogos/{product_id}",
            "quantity-discount": f"quantity-discount/{product_id}"
        }
        
        endpoint = endpoint_map.get(pricing_type)
        if not endpoint:
            return [TextContent(type="text", text=f"Error: Invalid pricing type: {pricing_type}")]
            
        pricing = nova_request("get", endpoint)
        if "error" in pricing:
            return [TextContent(type="text", text=f"Error: {pricing['error']}")]
        return [TextContent(type="text", text=json.dumps(pricing, indent=2))]

    elif name == "get_order_lead_time":
        order_id = arguments.get("order_id")
        lead_time = nova_request("get", f"fetch-order-lead-time/{order_id}")
        if "error" in lead_time:
            return [TextContent(type="text", text=f"Error: {lead_time['error']}")]
        return [TextContent(type="text", text=json.dumps(lead_time, indent=2))]

    elif name == "check_lead_time":
        order_id = arguments.get("order_id")
        status = nova_request("get", f"order/{order_id}/production-status", auth_type="api_key")
        if "error" in status:
            return [TextContent(type="text", text=f"Error: {status['error']}")]
        return [TextContent(type="text", text=json.dumps(status, indent=2))]

    elif name == "manage_mockups":
        order_id = arguments.get("order_id")
        action = arguments.get("action") # fetch, approve, revise
        notes = arguments.get("notes", "")

        if action == "fetch":
            mockups = nova_request("get", f"order/{order_id}/mockups", auth_type="api_key")
            if "error" in mockups:
                return [TextContent(type="text", text=f"Error: {mockups['error']}")]
            return [TextContent(type="text", text=json.dumps(mockups, indent=2))]
        
        elif action in ["approve", "revise"]:
            result = nova_request("post", f"order/{order_id}/mockup-feedback", data={"action": action, "notes": notes}, auth_type="api_key")
            if "error" in result:
                return [TextContent(type="text", text=f"Error: {result['error']}")]
            return [TextContent(type="text", text=f"Successfully submitted {action} for order {order_id}.")]
        
        else:
             return [TextContent(type="text", text=f"Error: Invalid action '{action}'. details: action must be one of 'fetch', 'approve', 'revise'.")]

    elif name == "get_product_knowledge":
        signage_id = arguments.get("signage_id")
        knowledge = nova_request("get", f"signage/{signage_id}/knowledge")
        if "error" in knowledge:
            return [TextContent(type="text", text=f"Error: {knowledge['error']}")]
        return [TextContent(type="text", text=json.dumps(knowledge, indent=2))]

    elif name == "get_business_id":
        email = arguments.get("email")
        user_id = arguments.get("user_id")
        
        if email:
            result = nova_request("get", f"businessId/{email}")
        elif user_id:
            result = nova_request("get", f"businessIdfromId/{user_id}")
        else:
            return [TextContent(type="text", text="Error: Either email or user_id is required")]
            
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_customer_profile":
        customer_id = arguments.get("id")
        email = arguments.get("email")
        business_id = arguments.get("business_id")
        
        params = {}
        if customer_id: params["id"] = customer_id
        if email: params["email"] = email
        if business_id: params["business_id"] = business_id
        
        if not params:
             return [TextContent(type="text", text="Error: One of id, email, or business_id is required")]
             
        result = nova_request("get", "customer-profile", params=params)
        if "error" in result:
             return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    elif name == "get_user_orders":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"user/{user_id}/orders")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_order_total":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"user/{user_id}/order-total")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_average_order":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"user/{user_id}/average-order")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_ticket_details":
        ticket_id = arguments.get("ticket_id")
        email = arguments.get("email")
        result = nova_request("get", f"ticket-details/{ticket_id}", params={"email": email} if email else None, auth_type="basic")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_details":
        user_id = arguments.get("user_id")
        email = arguments.get("email")
        result = nova_request("get", f"user-details/{user_id}", params={"email": email} if email else None, auth_type="basic")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_order_details":
        order_id = arguments.get("order_id")
        result = nova_request("get", f"order/{order_id}", auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Edit tools (Implemented but not registered in list_tools to remain "uncallable" via discovery)
    elif name == "link_zendesk_ticket":
        order_id = arguments.get("order_id")
        ticket_id = arguments.get("ticket_id")
        result = nova_request("post", "update-order-mcp", data={"subject": str(order_id), "ticket_id": str(ticket_id)}, auth_type="basic")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Successfully linked ticket {ticket_id} to order {order_id}.")]

    elif name == "ocr_business_card":
        file_url = arguments.get("file_url")
        result = nova_request("post", "ocr/business-card", data={"file_url": file_url}, auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_quotes":
        per_page = arguments.get("per_page", 10)
        search = arguments.get("search", None)
        
        params = {"per_page": per_page}
        if search:
            params["search"] = search
            
        quotes = wp_get("nova_quote", params)
        
        if isinstance(quotes, dict) and "error" in quotes:
            return [TextContent(type="text", text=f"Error: {quotes['error']}")]
        
        # Format quote data
        result = []
        for q in quotes:
            result.append({
                "id": q.get("id"),
                "title": q.get("title", {}).get("rendered"),
                "date": q.get("date"),
                "status": q.get("status"),
                "link": q.get("link"),
                "acf": q.get("acf", {}) # Included if ACF "Show in REST API" is enabled
            })
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_quote":
        quote_id = arguments.get("quote_id")
        if not quote_id:
            return [TextContent(type="text", text="Error: quote_id is required")]
            
        quote = wp_get(f"nova_quote/{quote_id}")
        
        if "error" in quote:
            return [TextContent(type="text", text=f"Error: {quote['error']}")]
            
        # Format detailed quote data
        result = {
            "id": quote.get("id"),
            "title": quote.get("title", {}).get("rendered"),
            "content": quote.get("content", {}).get("rendered"),
            "date": quote.get("date"),
            "status": quote.get("status"),
            "acf": quote.get("acf", {}),
            "meta": quote.get("meta", {})
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_quotes":
        user_id = arguments.get("user_id")
        if not user_id:
            return [TextContent(type="text", text="Error: user_id is required")]
            
        quotes = nova_request("get", f"user/{user_id}/quotes")
        
        if "error" in quotes:
            return [TextContent(type="text", text=f"Error: {quotes['error']}")]
            
        return [TextContent(type="text", text=json.dumps(quotes, indent=2))]


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
                    "per_page": {"type": "number", "description": "Number of products to retrieve (max 100)", "default": 10},
                    "category": {"type": "string", "description": "Filter by category ID"}
                }
            }
        ),
        Tool(
            name="get_orders",
            description="Get orders from WooCommerce store. Supports filtering by status, date, and search terms.",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {"type": "number", "default": 10},
                    "status": {"type": "string", "description": "any, pending, processing, on-hold, completed, cancelled, refunded, failed"},
                    "after": {"type": "string", "description": "ISO 8601 date to get orders after"},
                    "before": {"type": "string", "description": "ISO 8601 date to get orders before"},
                    "search": {"type": "string", "description": "Search term for orders"},
                    "customer": {"type": "number", "description": "Filter by customer ID"}
                }
            }
        ),
        Tool(
            name="update_order_status",
            description="Update the status of an existing order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "status": {"type": "string", "enum": ["pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"]}
                },
                "required": ["order_id", "status"]
            }
        ),
        Tool(
            name="get_order_notes",
            description="Retrieve notes for a specific order.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
            }
        ),
        Tool(
            name="add_order_note",
            description="Add a new note to an order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "note": {"type": "string"},
                    "customer_note": {"type": "boolean", "default": False}
                },
                "required": ["order_id", "note"]
            }
        ),
        Tool(
            name="create_order_refund",
            description="Create a refund for an order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "amount": {"type": "number"},
                    "reason": {"type": "string"}
                },
                "required": ["order_id", "amount"]
            }
        ),
        Tool(
            name="get_top_selling_products",
            description="Get top selling products by popularity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "default": 10},
                    "period": {"type": "string", "enum": ["day", "week", "month", "year"], "default": "month"}
                }
            }
        ),
        Tool(
            name="get_revenue_by_category",
            description="Get sales revenue report grouped by product categories.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_customer_lvt",
            description="Analyze Customer Lifetime Value (total spent and order history).",
            inputSchema={
                "type": "object",
                "properties": {"customer_id": {"type": "number"}},
                "required": ["customer_id"]
            }
        ),
        Tool(
            name="compare_sales_periods",
            description="Compare revenue and order count between two time periods.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period1_after": {"type": "string", "description": "ISO 8601 start date for Period 1"},
                    "period1_before": {"type": "string", "description": "ISO 8601 end date for Period 1"},
                    "period2_after": {"type": "string", "description": "ISO 8601 start date for Period 2"},
                    "period2_before": {"type": "string", "description": "ISO 8601 end date for Period 2"}
                },
                "required": ["period1_after", "period1_before", "period2_after", "period2_before"]
            }
        ),
        Tool(
            name="get_coupon_performance",
            description="Get usage statistics for coupons.",
            inputSchema={
                "type": "object",
                "properties": {"coupon_code": {"type": "string", "description": "Optional specific coupon code"}}
            }
        ),
        Tool(
            name="get_customer_profile",
            description="Get detailed profile for a customer by ID or email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "number"},
                    "email": {"type": "string"}
                }
            }
        ),
        Tool(
            name="get_product_reviews",
            description="Get product reviews.",
            inputSchema={
                "type": "object",
                "properties": {"product_id": {"type": "number"}}
            }
        ),
        Tool(
            name="get_frequent_buyers",
            description="Find customers with high order frequency.",
            inputSchema={
                "type": "object",
                "properties": {"order_threshold": {"type": "number", "default": 3}}
            }
        ),
        Tool(
            name="update_product_stock",
            description="Update stock quantity for a product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "number"},
                    "stock_quantity": {"type": "number"}
                },
                "required": ["product_id", "stock_quantity"]
            }
        ),
        Tool(
            name="get_product_variations",
            description="Get variations for a variable product.",
            inputSchema={
                "type": "object",
                "properties": {"product_id": {"type": "number"}},
                "required": ["product_id"]
            }
        ),
        Tool(
            name="toggle_product_visibility",
            description="Set product status (publish, draft, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "number"},
                    "status": {"type": "string", "enum": ["publish", "draft", "pending", "private"]}
                },
                "required": ["product_id", "status"]
            }
        ),
        Tool(
            name="create_coupon",
            description="Create a new discount coupon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "amount": {"type": "number"},
                    "discount_type": {"type": "string", "enum": ["percent", "fixed_cart", "fixed_product"], "default": "percent"},
                    "description": {"type": "string"}
                },
                "required": ["code", "amount"]
            }
        ),
        Tool(
            name="get_active_coupons",
            description="List all active (non-expired) coupons.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_sales_trends",
            description="Analyze sales trends over a specified time period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "number", "default": 30}
                }
            }
        ),
        Tool(
            name="get_low_stock_products",
            description="Find products with low stock levels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "default": 10}
                }
            }
        ),
        Tool(
            name="get_all_orders",
            description="List live orders with physical material details and customer information. Requires API Key.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_product_pricing",
            description="Retrieve pricing tables or discount rules for a specific product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "number"},
                    "type": {"type": "string", "enum": ["letters", "multi-letters", "logos", "quantity-discount"], "default": "letters"}
                },
                "required": ["product_id"]
            }
        ),
        Tool(
            name="link_zendesk_ticket",
            description="Automate the connection between support tickets and physical orders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "ticket_id": {"type": "number"}
                },
                "required": ["order_id", "ticket_id"]
            }
        ),
        Tool(
            name="check_lead_time",
            description="Get detailed production timeline and estimated lead times for an order.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
            }
        ),
         Tool(
            name="manage_mockups",
            description="Allow AI to help customers review and approve their signage designs safely.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "action": {"type": "string", "enum": ["fetch", "approve", "revise"], "description": "Action to perform: fetch links, approve design, or request revision"},
                    "notes": {"type": "string", "description": "Notes for approval or revision (required for approve/revise)"}
                },
                "required": ["order_id", "action"]
            }
        ),
        Tool(
            name="get_product_knowledge",
            description="Get technical specs, FAQs, and installation guides for a signage product.",
            inputSchema={
                "type": "object",
                "properties": {"signage_id": {"type": "number"}},
                "required": ["signage_id"]
            }
        ),
        Tool(
            name="get_customer_profile",
             description="Get detailed profile for a customer by ID or email. Unified endpoint for all customer lookups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "number", "description": "Twilio/WordPress User ID"},
                    "email": {"type": "string"},
                    "business_id": {"type": "string"}
                },
                 "description": "Provide at least one of id, email, or business_id"
            }
        ),
         Tool(
            name="get_user_orders",
            description="Get count of orders for a specific user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "number"}
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_user_order_total",
            description="Get total spending for a specific user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "number"}
                },
                "required": ["user_id"]
            }
        ),
         Tool(
            name="get_user_quotes",
            description="Retrieve all quotes associated with a specific user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "number"}
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_user_average_order",
            description="Get average order value for a specific user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "number"}
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_ticket_details",
            description="Get detailed information for a Zendesk ticket. Requires Application Password.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "email": {"type": "string", "description": "Admin email for auth verification"}
                },
                "required": ["ticket_id"]
            }
        ),
        Tool(
            name="get_user_details",
            description="Get detailed information for a Zendesk user. Requires Application Password.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "email": {"type": "string", "description": "Admin email for auth verification"}
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_order_details",
            description="Get detailed information for a specific order.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
            }
        ),
        Tool(
            name="get_quotes",
            description="List all signage quotes from the WordPress site. Supports pagination and keyword searching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {"type": "number", "description": "Number of quotes to retrieve (max 100)", "default": 10},
                    "search": {"type": "string", "description": "Search term to filter quotes by title or content"}
                }
            }
        ),
        Tool(
            name="get_quote",
            description="Get detailed information for a specific quote by ID, including technical configuration (ACF fields).",
            inputSchema={
                "type": "object",
                "properties": {
                    "quote_id": {"type": "number", "description": "The unique ID of the quote post"}
                },
                "required": ["quote_id"]
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