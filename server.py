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
from zendesk_tools import handle_zendesk_tool, get_zendesk_tool_definitions
from zendesk_sell_tools import handle_zendesk_sell_tool, get_zendesk_sell_tool_definitions

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
    
    # Handle Zendesk tools
    if name.startswith("search_zendesk") or name.startswith("get_zendesk") or name == "add_zendesk_ticket_comment":
        if "_sell_" in name:
            return await handle_zendesk_sell_tool(name, arguments)
        return await handle_zendesk_tool(name, arguments)

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
        orders = nova_request("get", "mcp/nova_orders", auth_type="api_key")
        if "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
        return [TextContent(type="text", text=json.dumps(orders, indent=2))]

    elif name == "get_product_pricing":
        product_id = arguments.get("product_id")
        pricing_type = arguments.get("type", "letters") # letters, multi-letters, logos, quantity-discount
        
        endpoint_map = {
            "letters": f"mcp/pricingletters/{product_id}",
            "multi-letters": f"mcp/multipricingletters/{product_id}",
            "logos": f"mcp/pricinglogos/{product_id}",
            "quantity-discount": f"mcp/quantity-discount/{product_id}"
        }
        
        endpoint = endpoint_map.get(pricing_type)
        if not endpoint:
            return [TextContent(type="text", text=f"Error: Invalid pricing type: {pricing_type}")]
            
        pricing = nova_request("get", endpoint, auth_type="api_key")
        if "error" in pricing:
            return [TextContent(type="text", text=f"Error: {pricing['error']}")]
        return [TextContent(type="text", text=json.dumps(pricing, indent=2))]

    elif name == "get_order_lead_time":
        order_id = arguments.get("order_id")
        lead_time = nova_request("get", f"mcp/fetch-order-lead-time/{order_id}", auth_type="api_key")
        if "error" in lead_time:
            return [TextContent(type="text", text=f"Error: {lead_time['error']}")]
        return [TextContent(type="text", text=json.dumps(lead_time, indent=2))]

    elif name == "check_lead_time":
        order_id = arguments.get("order_id")
        status = nova_request("get", f"mcp/order/{order_id}/production-status", auth_type="api_key")
        if "error" in status:
            return [TextContent(type="text", text=f"Error: {status['error']}")]
        return [TextContent(type="text", text=json.dumps(status, indent=2))]

    elif name == "manage_mockups":
        order_id = arguments.get("order_id")
        action = arguments.get("action") # fetch
        # Restricted to fetch only
        if action == "fetch":
            mockups = nova_request("get", f"mcp/order/{order_id}/mockups", auth_type="api_key")
            if "error" in mockups:
                return [TextContent(type="text", text=f"Error: {mockups['error']}")]
            return [TextContent(type="text", text=json.dumps(mockups, indent=2))]
        else:
             return [TextContent(type="text", text=f"Error: Action '{action}' is not supported or allowed.")]

    elif name == "get_product_knowledge":
        signage_id = arguments.get("signage_id")
        knowledge = nova_request("get", f"mcp/signage/{signage_id}/knowledge", auth_type="api_key")
        if "error" in knowledge:
            return [TextContent(type="text", text=f"Error: {knowledge['error']}")]
        return [TextContent(type="text", text=json.dumps(knowledge, indent=2))]

    elif name == "get_business_id":
        email = arguments.get("email")
        user_id = arguments.get("user_id")
        
        if email:
            result = nova_request("get", f"mcp/businessId/{email}", auth_type="api_key")
        elif user_id:
            result = nova_request("get", f"mcp/businessIdfromId/{user_id}", auth_type="api_key")
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
             
        result = nova_request("get", "mcp/customer-profile", params=params, auth_type="api_key")
        if "error" in result:
             return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    elif name == "get_user_orders":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"mcp/user/{user_id}/orders", auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_order_total":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"mcp/user/{user_id}/order-total", auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_user_average_order":
        user_id = arguments.get("user_id")
        result = nova_request("get", f"mcp/user/{user_id}/average-order", auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_order_details":
        order_id = arguments.get("order_id")
        result = nova_request("get", f"mcp/order/{order_id}", auth_type="api_key")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_public_orders":
        result = nova_request("get", "mcp/orders")
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
        email = arguments.get("email")
        business_id = arguments.get("business_id")
        
        params = {}
        if user_id: params["id"] = user_id
        if email: params["email"] = email
        if business_id: params["business_id"] = business_id
        
        if not params:
            return [TextContent(type="text", text="Error: One of user_id, email, or business_id is required")]
            
        quotes = nova_request("get", "mcp/user/quotes", params=params, auth_type="api_key")
        
        if "error" in quotes:
            return [TextContent(type="text", text=f"Error: {quotes['error']}")]
            
        return [TextContent(type="text", text=json.dumps(quotes, indent=2))]

    elif name == "get_refund_analytics":
        period = arguments.get("period", "last_month")
        refund_type = arguments.get("type", "all")
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")
        
        params = {"period": period, "type": refund_type}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        result = nova_request("get", "mcp/analytics/refunds", params=params, auth_type="api_key")
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_inactive_clients":
        days = arguments.get("days", 60)
        activity_type = arguments.get("activity_type", "quotes")
        per_page = arguments.get("per_page", 50)
        page = arguments.get("page", 1)
        
        params = {
            "days": days,
            "activity_type": activity_type,
            "per_page": per_page,
            "page": page
        }
        
        result = nova_request("get", "mcp/analytics/inactive-clients", params=params, auth_type="api_key")
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "search_customers":
        business_name = arguments.get("business_name")
        business_type = arguments.get("business_type")
        country = arguments.get("country")
        state = arguments.get("state")
        per_page = arguments.get("per_page", 50)
        page = arguments.get("page", 1)
        
        params = {"per_page": per_page, "page": page}
        if business_name:
            params["business_name"] = business_name
        if business_type:
            params["business_type"] = business_type
        if country:
            params["country"] = country
        if state:
            params["state"] = state
            
        result = nova_request("get", "mcp/customers/search", params=params, auth_type="api_key")
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "list_all_business_ids":
        result = nova_request("get", "mcp/show-all-business-id/", auth_type="api_key")
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_top_selling_products":
        limit = arguments.get("limit", 10)
        period = arguments.get("period", "month")
        result = wc_get("reports/top_sellers", {"period": period, "per_page": limit})
        if isinstance(result, dict) and "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_revenue_by_category":
        categories = wc_get("products/categories", {"per_page": 100})
        if isinstance(categories, dict) and "error" in categories:
            return [TextContent(type="text", text=f"Error: {categories['error']}")]
        result = []
        for cat in categories:
            cat_id = cat.get("id")
            cat_name = cat.get("name")
            products = wc_get("products", {"category": cat_id, "per_page": 100})
            if isinstance(products, list):
                total_sales = sum(float(p.get("total_sales", 0)) * float(p.get("price", 0) or 0) for p in products)
                result.append({"category": cat_name, "product_count": len(products), "estimated_revenue": round(total_sales, 2)})
        result.sort(key=lambda x: x["estimated_revenue"], reverse=True)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "analyze_customer_lvt":
        customer_id = arguments.get("customer_id")
        if not customer_id:
            return [TextContent(type="text", text="Error: customer_id is required")]
        orders = wc_get("orders", {"customer": customer_id, "per_page": 100, "status": "completed"})
        if isinstance(orders, dict) and "error" in orders:
            return [TextContent(type="text", text=f"Error: {orders['error']}")]
        total_spent = sum(float(o.get("total", 0)) for o in orders)
        result = {
            "customer_id": customer_id,
            "total_orders": len(orders),
            "total_spent": round(total_spent, 2),
            "average_order_value": round(total_spent / len(orders), 2) if orders else 0,
            "first_order": orders[-1].get("date_created") if orders else None,
            "last_order": orders[0].get("date_created") if orders else None,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "compare_sales_periods":
        p1_after = arguments.get("period1_after")
        p1_before = arguments.get("period1_before")
        p2_after = arguments.get("period2_after")
        p2_before = arguments.get("period2_before")
        if not all([p1_after, p1_before, p2_after, p2_before]):
            return [TextContent(type="text", text="Error: All four date parameters are required")]
        p1_orders = wc_get("orders", {"after": p1_after, "before": p1_before, "status": "completed", "per_page": 100})
        p2_orders = wc_get("orders", {"after": p2_after, "before": p2_before, "status": "completed", "per_page": 100})
        def summarize(orders):
            if isinstance(orders, dict) and "error" in orders:
                return {"error": orders["error"]}
            revenue = sum(float(o.get("total", 0)) for o in orders)
            return {"order_count": len(orders), "revenue": round(revenue, 2), "avg_order_value": round(revenue / len(orders), 2) if orders else 0}
        result = {"period1": {"from": p1_after, "to": p1_before, **summarize(p1_orders)},
                  "period2": {"from": p2_after, "to": p2_before, **summarize(p2_orders)}}
        if "error" not in result["period1"] and "error" not in result["period2"]:
            rev_change = result["period2"]["revenue"] - result["period1"]["revenue"]
            result["comparison"] = {"revenue_change": round(rev_change, 2),
                                     "revenue_change_pct": round((rev_change / result["period1"]["revenue"]) * 100, 1) if result["period1"]["revenue"] else None}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_coupon_performance":
        coupon_code = arguments.get("coupon_code")
        params = {"per_page": 100}
        if coupon_code:
            params["code"] = coupon_code
        coupons = wc_get("coupons", params)
        if isinstance(coupons, dict) and "error" in coupons:
            return [TextContent(type="text", text=f"Error: {coupons['error']}")]
        result = [{"id": c.get("id"), "code": c.get("code"), "discount_type": c.get("discount_type"),
                   "amount": c.get("amount"), "usage_count": c.get("usage_count"),
                   "usage_limit": c.get("usage_limit"), "date_expires": c.get("date_expires")} for c in coupons]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_product_reviews":
        product_id = arguments.get("product_id")
        params = {"per_page": 50}
        if product_id:
            params["product"] = product_id
        reviews = wc_get("products/reviews", params)
        if isinstance(reviews, dict) and "error" in reviews:
            return [TextContent(type="text", text=f"Error: {reviews['error']}")]
        result = [{"id": r.get("id"), "product_id": r.get("product_id"), "reviewer": r.get("reviewer"),
                   "rating": r.get("rating"), "review": r.get("review", {}).get("rendered", ""),
                   "date_created": r.get("date_created"), "verified": r.get("verified")} for r in reviews]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
            name="get_order_notes",
            description="Retrieve notes for a specific order.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
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
            name="get_product_variations",
            description="Get variations for a variable product.",
            inputSchema={
                "type": "object",
                "properties": {"product_id": {"type": "number"}},
                "required": ["product_id"]
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
            name="get_order_lead_time",
            description="Get the lead time status for an order from the Nova orders export.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
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
            description="Fetch mockup links for review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "number"},
                    "action": {"type": "string", "enum": ["fetch"], "description": "Action to perform: fetch links"}
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
            name="get_business_id",
            description="Find business ID by customer email or user ID. format: [Country][State]-[Business Type Initial][Sequence Number] (e.g., USNY-S001). Provide either email or user_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "user_id": {"type": "number"}
                }
            }
        ),
        Tool(
            name="get_customer_profile",
             description="Get detailed profile for a customer by ID or email. Unified endpoint for all customer lookups. Provide at least one of id, email, or business_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "number", "description": "Twilio/WordPress User ID"},
                    "email": {"type": "string"},
                    "business_id": {"type": "string", "description": "Business ID Format: [Country][State]-[Business Type Initial][Sequence Number] (e.g. USNY-S001)"}
                }
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
            description="Retrieve all quotes associated with a specific user by ID, email, or business ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "number", "description": "WordPress User ID"},
                    "email": {"type": "string", "description": "User email address"},
                    "business_id": {"type": "string", "description": "Business ID Format: [Country][State]-[Business Type Initial][Sequence Number]"}
                }
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
            name="get_order_details",
            description="Get detailed information for a specific order.",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "number"}},
                "required": ["order_id"]
            }
        ),
        Tool(
            name="get_public_orders",
            description="List live orders with production details. Public version of Nova orders.",
            inputSchema={"type": "object", "properties": {}}
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
        ),
        Tool(
            name="get_refund_analytics",
            description="Get refund analytics by time period and type (partial/full). Analyze refund patterns and track refund trends over time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["last_7_days", "last_30_days", "last_month", "custom"], "default": "last_month", "description": "Time period for analysis"},
                    "type": {"type": "string", "enum": ["all", "partial", "full"], "default": "all", "description": "Filter by refund type"},
                    "start_date": {"type": "string", "description": "ISO 8601 start date (required if period=custom)"},
                    "end_date": {"type": "string", "description": "ISO 8601 end date (required if period=custom)"}
                }
            }
        ),
        Tool(
            name="get_inactive_clients",
            description="Find customers without recent quotes/orders, segmented by purchase history. Identify customers who haven't quoted or ordered in X days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "number", "default": 60, "description": "Days of inactivity to check"},
                    "activity_type": {"type": "string", "enum": ["quotes", "orders", "both"], "default": "quotes", "description": "Type of activity to check"},
                    "per_page": {"type": "number", "default": 50, "description": "Results per page"},
                    "page": {"type": "number", "default": 1, "description": "Page number"}
                }
            }
        ),
        Tool(
            name="search_customers",
            description="Search and filter customers by business name, type, location, etc. Get full customer profiles with contact info, addresses, and stats.",
            inputSchema={
                "type": "object",
                "properties": {
                    "business_name": {"type": "string", "description": "Filter by business name (e.g., 'FASTSIGNS')"},
                    "business_type": {"type": "string", "description": "Filter by business type initial (e.g., 'S' for signage)"},
                    "country": {"type": "string", "description": "Filter by country code (e.g., 'US')"},
                    "state": {"type": "string", "description": "Filter by state code (e.g., 'NY')"},
                    "per_page": {"type": "number", "default": 50, "description": "Results per page"},
                    "page": {"type": "number", "default": 1, "description": "Page number"}
                }
            }
        ),
        Tool(
            name="list_all_business_ids",
            description="List all partners with their Business IDs and associated emails.",
            inputSchema={"type": "object", "properties": {}}
        )
    ] + get_zendesk_tool_definitions() + get_zendesk_sell_tool_definitions()


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