from woocommerce import API
from dotenv import load_dotenv
import os
import json
import requests
import base64

# Load environment variables
load_dotenv()

# Initialize WooCommerce API
wcapi = API(
    url=os.getenv("WC_URL"),
    consumer_key=os.getenv("WC_CONSUMER_KEY"),
    consumer_secret=os.getenv("WC_CONSUMER_SECRET"),
    version="wc/v3"
)

def test_woocommerce():
    print("Testing WooCommerce connection...")
    try:
        response = wcapi.get("products", params={"per_page": 1})
        if response.status_code == 200:
            print("OK: WooCommerce: Connection successful!")
            products = response.json()
            if products:
                print(f"OK: WooCommerce: Found sample product: {products[0].get('name')} (ID: {products[0].get('id')})")
        else:
            print(f"FAIL: WooCommerce: Failed (Status: {response.status_code})")
    except Exception as e:
        print(f"ERROR: WooCommerce: Error: {str(e)}")

def test_nova_api_discovery():
    base_url = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/nova/v1"
    print("\nDiscovering Nova B2B endpoints...")
    try:
        resp = requests.get(base_url)
        if resp.status_code == 200:
            routes = sorted(list(resp.json().get("routes", {}).keys()))
            print(f"OK: Nova: Found {len(routes)} routes in namespace.")
            print("Detected Routes:")
            for r in routes:
                print(f"  - {r}")
                
            has_ticket = any("ticket-details" in r for r in routes)
            if has_ticket:
                print("OK: Nova: Endpoint /ticket-details found.")
            else:
                # Try a simpler check
                has_ticket = any("ticket-details" in r for r in routes)
                if has_ticket:
                    print("OK: Nova: Endpoint /ticket-details found (approximate match).")
                else:
                    print("FAIL: Nova: Endpoint /ticket-details NOT found in discovery!")
        else:
            print(f"FAIL: Nova: Namespace discovery failed (Status: {resp.status_code})")
    except Exception as e:
        print(f"ERROR: Nova: Discovery error: {str(e)}")

def test_nova_api():
    base_url = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/nova/v1"
    api_key = os.getenv("NOVA_API_KEY")
    x_api_key = os.getenv("NOVAXAPIKEY")
    username = os.getenv("WP_USERNAME")
    password = os.getenv("WP_APP_PASSWORD")

    print("\nTesting Nova B2B custom endpoints...")
    
    # Test Public Endpoint
    try:
        resp = requests.get(f"{base_url}/orders")
        if resp.status_code == 200:
            print("OK: Nova: Public endpoint (/orders) accessible.")
        else:
            print(f"FAIL: Nova: Public endpoint failed (Status: {resp.status_code})")
    except Exception as e:
        print(f"ERROR: Nova: Public endpoint error: {str(e)}")

    # Test API Key Endpoint
    if api_key:
        try:
            # Test /nova_orders (GET)
            resp = requests.get(f"{base_url}/nova_orders", headers={"X-API-Key": api_key})
            if resp.status_code == 200:
                print("OK: Nova: API Key authentication successful (/nova_orders).")
            else:
                print(f"FAIL: Nova: API Key authentication failed for /nova_orders (Status: {resp.status_code})")

            # Test /priority (PUT) - just check auth
            resp = requests.put(f"{base_url}/priority/test@example.com", headers={"X-API-Key": api_key}, json={"priority": "low"})
            # We expect 404 (user not found) or success, but NOT 401
            if resp.status_code != 401:
                print(f"OK: Nova: API Key authentication accepted for /priority (Status: {resp.status_code}).")
            else:
                print("FAIL: Nova: API Key authentication failed for /priority (Status: 401)")

            # Test /streakBox (GET)
            resp = requests.get(f"{base_url}/streakBox/test", headers={"X-API-Key": api_key})
            if resp.status_code != 401:
                print(f"OK: Nova: API Key authentication accepted for /streakBox (Status: {resp.status_code}).")
            else:
                print("FAIL: Nova: API Key authentication failed for /streakBox (Status: 401)")

        except Exception as e:
            print(f"ERROR: Nova: API Key error: {str(e)}")
    else:
        print("! Nova: Skipping API Key test (NOVA_API_KEY not set).")

def test_zendesk():
    print("\nTesting Zendesk connection...")
    email = os.getenv("ZENDESK_EMAIL")
    token = os.getenv("ZENDESK_API_TOKEN")
    domain = "novasignagehelp.zendesk.com"
    
    if not email or not token:
        print("! Zendesk: Skipping test (ZENDESK_EMAIL or ZENDESK_API_TOKEN not set).")
        return

    auth_str = f"{email}/token:{token}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }
    
    try:
        # Test by fetching the current user
        resp = requests.get(f"https://{domain}/api/v2/users/me.json", headers=headers)
        if resp.status_code == 200:
            user = resp.json().get("user", {})
            print(f"OK: Zendesk: Connection successful! Authenticated as: {user.get('name')} ({user.get('email')})")
        else:
            print(f"FAIL: Zendesk: Authentication failed (Status: {resp.status_code})")
            try:
                error_msg = resp.json().get("description", resp.text)
                print(f"Details: {error_msg}")
            except:
                print(f"Response: {resp.text}")
    except Exception as e:
        print(f"ERROR: Zendesk: Error: {str(e)}")

def test_zendesk_sell():
    print("\nTesting Zendesk Sell connection...")
    token = os.getenv("ZENDESK_SELL_API_TOKEN")
    
    if not token:
        print("! Zendesk Sell: Skipping test (ZENDESK_SELL_API_TOKEN not set).")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        # Test by fetching the current user (sync account)
        resp = requests.get("https://api.getbase.com/v2/accounts/self", headers=headers)
        if resp.status_code == 200:
            account = resp.json().get("data", {})
            print(f"OK: Zendesk Sell: Connection successful! Account: {account.get('name')}")
        else:
            print(f"FAIL: Zendesk Sell: Authentication failed (Status: {resp.status_code})")
            try:
                print(f"Details: {resp.json().get('errors')}")
            except:
                print(f"Response: {resp.text}")
    except Exception as e:
        print(f"ERROR: Zendesk Sell: Error: {str(e)}")

def test_zendesk_tools():
    print("\nTesting Zendesk MCP Tools functionality...")
    from zendesk_tools import handle_zendesk_tool
    import asyncio

    async def run_tests():
        # 1. Test search_zendesk_tickets
        print("Testing: search_zendesk_tickets (query='status:open')...")
        results = await handle_zendesk_tool("search_zendesk_tickets", {"query": "status:open"})
        content = results[0].text
        data = json.loads(content)
        if "error" in data:
            print(f"FAIL: search_zendesk_tickets: {data['error']}")
        else:
            count = data.get("count", 0)
            print(f"OK: search_zendesk_tickets: Found {count} open tickets.")
            
            if count > 0:
                ticket_id = data["results"][0]["id"]
                # 2. Test get_zendesk_ticket_comments
                print(f"Testing: get_zendesk_ticket_comments (ID: {ticket_id})...")
                comments_results = await handle_zendesk_tool("get_zendesk_ticket_comments", {"ticket_id": str(ticket_id)})
                comments_data = json.loads(comments_results[0].text)
                if "error" in comments_data:
                    print(f"FAIL: get_zendesk_ticket_comments: {comments_data['error']}")
                else:
                    print(f"OK: get_zendesk_ticket_comments: Found {len(comments_data.get('comments', []))} comments.")

        # 3. Test search_zendesk_users
        print("Testing: search_zendesk_users (query='Lok')...")
        user_results = await handle_zendesk_tool("search_zendesk_users", {"query": "Lok"})
        user_data = json.loads(user_results[0].text)
        if "error" in user_data:
            print(f"FAIL: search_zendesk_users: {user_data['error']}")
        else:
            print(f"OK: search_zendesk_users: Found {user_data.get('count', 0)} users matching 'Lok'.")

    asyncio.run(run_tests())

if __name__ == "__main__":
    test_woocommerce()
    test_nova_api_discovery()
    test_nova_api()
    test_zendesk()
    test_zendesk_sell()
    test_zendesk_tools()